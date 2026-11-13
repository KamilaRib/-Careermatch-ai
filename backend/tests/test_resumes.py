from __future__ import annotations

import io
from typing import TypeVar

import httpx
import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from pydantic import BaseModel
from reportlab.pdfgen import canvas

from app.ai.providers.base import get_llm_provider, parse_and_validate_json
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.validators.evidence_validator import validate_resume_evidence
from app.core.config import Settings
from app.core.errors import AIUnavailableError, ValidationFailed
from app.main import create_app
from app.schemas.resume import (
    CertificationItem,
    EducationItem,
    ExperienceItem,
    LanguageItem,
    ParsedResumeData,
    PersonalInfo,
    ProjectItem,
    SkillItem,
)
from tests.conftest import csrf_headers

T = TypeVar("T", bound=BaseModel)

SAMPLE_RESUME_TEXT = """Ana Carolina Mendes
São Paulo - SP | ana.mendes@email.com | (11) 98765-4321 | linkedin.com/in/anacarolinamendes

Resumo Profissional
Engenheira de Software Backend com 6 anos de experiência no desenvolvimento de APIs REST em Python e FastAPI, arquitetura de microsserviços e bancos de dados relacionais PostgreSQL.

Experiência Profissional
Engenheira Backend Sênior | TechNova Soluções | 2022 - Atual
- Liderou a migração de serviços legados para FastAPI e Python 3.12.
- Implementou pipelines de integração contínua e testes automatizados com pytest.

Desenvolvedora Python Pleno | DataCloud Brasil | 2019 - 2022
- Desenvolveu rotinas de processamento de dados e integrações REST com clientes corporativos.

Formação Acadêmica
Bacharelado em Ciência da Computação | Universidade de São Paulo | 2015 - 2018

Competências Técnicas
Python, FastAPI, PostgreSQL, Docker, Git, Pytest

Certificações
AWS CertifiedCloud Practitioner - 2023

Idiomas
Português: Nativo, Inglês: Avançado

Projetos
API Gateway Financeiro - Serviço de roteamento e autenticação de transações em Python e FastAPI.
"""


def _make_pdf_with_text(text: str) -> bytes:
    import textwrap

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for raw_line in text.splitlines():
        wrapped = textwrap.wrap(
            raw_line, width=85, break_long_words=False, break_on_hyphens=False
        ) or [""]
        for line in wrapped:
            c.drawString(50, y, line)
            y -= 14
            if y < 60:
                c.showPage()
                y = 780
    c.save()
    return buf.getvalue()


def _make_blank_scanned_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    # Page with only graphics and no extractable text
    c.rect(50, 50, 200, 200, stroke=1, fill=0)
    c.showPage()
    c.save()
    return buf.getvalue()


def _make_docx_with_text(text: str) -> bytes:
    buf = io.BytesIO()
    doc = DocxDocument()
    for line in text.splitlines():
        if line.strip():
            doc.add_paragraph(line)
    doc.save(buf)
    return buf.getvalue()


class FakeLLMProvider:
    """Explicit test mock for LLMProvider (never used in production flows)."""

    name = "mock_ollama"
    model = "llama3.2-test"

    def __init__(self, result: ParsedResumeData | Exception) -> None:
        self._result = result

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        assert "<curriculo_bruto>" in user_prompt
        if isinstance(self._result, Exception):
            raise self._result
        return self._result  # type: ignore[return-value]


def test_upload_pdf_docx_and_txt_extracts_text(client: TestClient) -> None:
    headers = csrf_headers(client)

    # 1. PDF
    pdf_bytes = _make_pdf_with_text(SAMPLE_RESUME_TEXT)
    r_pdf = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("curriculo_ana.pdf", pdf_bytes, "application/pdf")},
        headers=headers,
    )
    assert r_pdf.status_code == 200
    body_pdf = r_pdf.json()
    assert body_pdf["kind"] == "pdf"
    assert "Ana Carolina Mendes" in body_pdf["raw_text"]

    # 2. DOCX
    docx_bytes = _make_docx_with_text(SAMPLE_RESUME_TEXT)
    r_docx = client.post(
        "/api/v1/resumes/upload",
        files={
            "file": (
                "curriculo_ana.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=headers,
    )
    assert r_docx.status_code == 200
    assert r_docx.json()["kind"] == "docx"
    assert "FastAPI" in r_docx.json()["raw_text"]

    # 3. TXT
    r_txt = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("curriculo_ana.txt", SAMPLE_RESUME_TEXT.encode("utf-8"), "text/plain")},
        headers=headers,
    )
    assert r_txt.status_code == 200
    assert r_txt.json()["kind"] == "txt"
    assert r_txt.json()["char_count"] == len(SAMPLE_RESUME_TEXT.strip())


def test_upload_scanned_pdf_without_text_returns_ocr_not_available(client: TestClient) -> None:
    headers = csrf_headers(client)
    scanned_pdf = _make_blank_scanned_pdf()
    r = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("digitalizado.pdf", scanned_pdf, "application/pdf")},
        headers=headers,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ocr_not_available"


def test_parse_with_llm_and_evidence_verification(client: TestClient) -> None:
    headers = csrf_headers(client)
    mock_data = ParsedResumeData(
        personal_info=PersonalInfo(
            full_name="Ana Carolina Mendes",
            email="ana.mendes@email.com",
            phone="(11) 98765-4321",
            linkedin="linkedin.com/in/anacarolinamendes",
            location="São Paulo - SP",
            evidence_quote="Ana Carolina Mendes | São Paulo - SP | ana.mendes@email.com",
        ),
        professional_summary="Engenheira de Software Backend com 6 anos de experiência.",
        summary_evidence_quote="Engenheira de Software Backend com 6 anos de experiência",
        experiences=[
            ExperienceItem(
                role="Engenheira Backend Sênior",
                company="TechNova Soluções",
                period="2022 - Atual",
                responsibilities=["Liderou a migração de serviços legados para FastAPI e Python 3.12."],
                evidence_quote="Engenheira Backend Sênior | TechNova Soluções | 2022 - Atual",
            ),
            # Intentionally fabricated item to verify deterministic evidence flag
            ExperienceItem(
                role="Diretora de Inteligência Quântica",
                company="Empresa Inexistente XYZ",
                period="2025",
                responsibilities=["Inventado pela IA"],
                evidence_quote="Diretora de Inteligência Quântica na Empresa Inexistente XYZ",
            ),
        ],
        education=[
            EducationItem(
                degree="Bacharelado em Ciência da Computação",
                institution="Universidade de São Paulo",
                period="2015 - 2018",
                evidence_quote="Bacharelado em Ciência da Computação | Universidade de São Paulo | 2015 - 2018",
            )
        ],
        technical_skills=[
            SkillItem(name="Python", evidence_quote="Python, FastAPI, PostgreSQL"),
            SkillItem(name="Kubernetes", evidence_quote="Kubernetes cluster administration"),
        ],
        certifications=[
            CertificationItem(
                name="AWS CertifiedCloud Practitioner",
                year="2023",
                evidence_quote="AWS CertifiedCloud Practitioner - 2023",
            )
        ],
        languages=[
            LanguageItem(
                language="Inglês",
                proficiency="Avançado",
                evidence_quote="Português: Nativo, Inglês: Avançado",
            )
        ],
        projects=[
            ProjectItem(
                name="API Gateway Financeiro",
                description="Serviço de roteamento e autenticação de transações",
                evidence_quote="API Gateway Financeiro - Serviço de roteamento",
            )
        ],
    )
    client.app.state.llm_provider = FakeLLMProvider(mock_data)

    r = client.post(
        "/api/v1/resumes/parse",
        json={"text": SAMPLE_RESUME_TEXT},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["extraction_method"] == "llm"
    assert body["provider_used"] == "mock_ollama:llama3.2-test"
    assert body["confirmed"] is False

    # First experience is grounded; second is fabricated and must be flagged
    exps = body["data"]["experiences"]
    assert exps[0]["evidence_verified"] is True
    assert exps[1]["evidence_verified"] is False

    # Python is grounded; Kubernetes is fabricated and must be flagged
    skills = body["data"]["technical_skills"]
    assert skills[0]["evidence_verified"] is True
    assert skills[1]["evidence_verified"] is False

    report = body["evidence_report"]
    assert report["total_items_checked"] == 8
    assert report["verified_items"] == 6
    assert len(report["unverified_warnings"]) == 2


def test_parse_falls_back_to_deterministic_when_ollama_unavailable(client: TestClient) -> None:
    headers = csrf_headers(client)
    client.app.state.llm_provider = FakeLLMProvider(
        AIUnavailableError("Servidor Ollama local indisponível em http://localhost:11434.")
    )

    r = client.post(
        "/api/v1/resumes/parse",
        json={"text": SAMPLE_RESUME_TEXT},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    # Explicitly labeled as deterministic fallback, never misrepresented as LLM
    assert body["extraction_method"] == "deterministic_fallback"
    assert body["provider_used"] == "deterministic"
    assert "Ollama" in body["provider_fallback_reason"]

    data = body["data"]
    assert data["personal_info"]["full_name"] == "Ana Carolina Mendes"
    assert data["personal_info"]["email"] == "ana.mendes@email.com"
    assert len(data["experiences"]) == 2
    assert data["experiences"][0]["role"] == "Engenheira Backend Sênior"
    assert data["experiences"][0]["company"] == "TechNova Soluções"
    assert len(data["education"]) == 1
    assert any(s["name"] == "FastAPI" for s in data["technical_skills"])
    assert body["evidence_report"]["unverified_warnings"] == []


def test_review_and_confirm_resume_and_session_isolation(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client_a, TestClient(app) as client_b:
        headers_a = csrf_headers(client_a)
        headers_b = csrf_headers(client_b)

        # Client A parses a resume in deterministic mode
        r_parse = client_a.post(
            "/api/v1/resumes/parse",
            json={"text": SAMPLE_RESUME_TEXT, "use_deterministic_only": True},
            headers=headers_a,
        )
        assert r_parse.status_code == 200
        parsed_data = r_parse.json()["data"]

        # Client B must NOT see Client A's resume
        r_b = client_b.get("/api/v1/resumes/current")
        assert r_b.status_code == 200
        assert r_b.json()["has_resume"] is False
        assert r_b.json()["data"] is None

        # Client A edits and confirms the resume
        parsed_data["personal_info"]["full_name"] = "Ana Carolina M. Silva"
        r_put = client_a.put(
            "/api/v1/resumes/current",
            json={"data": parsed_data, "confirmed": True},
            headers=headers_a,
        )
        assert r_put.status_code == 200
        assert r_put.json()["confirmed"] is True
        assert r_put.json()["data"]["personal_info"]["full_name"] == "Ana Carolina M. Silva"


def test_parse_and_validate_json_handles_malformed_and_schema_errors() -> None:
    with pytest.raises(ValidationFailed) as exc_empty:
        parse_and_validate_json("", ParsedResumeData, "ollama")
    assert exc_empty.value.code == "ai_empty_response"

    with pytest.raises(ValidationFailed) as exc_json:
        parse_and_validate_json("{not valid json", ParsedResumeData, "ollama")
    assert exc_json.value.code == "ai_invalid_json"

    with pytest.raises(ValidationFailed) as exc_schema:
        parse_and_validate_json('{"experiences": "should_be_a_list"}', ParsedResumeData, "ollama")
    assert exc_schema.value.code == "ai_schema_validation_failed"


@pytest.mark.asyncio
async def test_ollama_gemini_and_openai_providers_with_mock_transport() -> None:
    valid_json = ParsedResumeData(
        personal_info=PersonalInfo(full_name="Teste Provider")
    ).model_dump_json()

    # 1. Ollama mock transport
    def ollama_handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"content": valid_json}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(ollama_handler)) as http:
        ollama = OllamaProvider(base_url="http://localhost:11434", http_client=http)
        out1 = await ollama.generate_structured(
            system_prompt="sys", user_prompt="usr", schema=ParsedResumeData
        )
        assert out1.personal_info.full_name == "Teste Provider"

    # 2. Gemini mock transport (ensures key is in header x-goog-api-key, never in URL query)
    def gemini_handler(req: httpx.Request) -> httpx.Response:
        assert "key=" not in str(req.url)
        assert req.headers.get("x-goog-api-key") == "AIzaSyTestKey123456"
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": valid_json}]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(gemini_handler)) as http:
        gemini = GeminiProvider(api_key="AIzaSyTestKey123456", http_client=http)
        out2 = await gemini.generate_structured(
            system_prompt="sys", user_prompt="usr", schema=ParsedResumeData
        )
        assert out2.personal_info.full_name == "Teste Provider"

    # 3. OpenAI mock transport
    def openai_handler(req: httpx.Request) -> httpx.Response:
        assert req.headers.get("Authorization") == "Bearer sk-testkey123456"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": valid_json}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(openai_handler)) as http:
        openai = OpenAIProvider(api_key="sk-testkey123456", http_client=http)
        out3 = await openai.generate_structured(
            system_prompt="sys", user_prompt="usr", schema=ParsedResumeData
        )
        assert out3.personal_info.full_name == "Teste Provider"


def test_provider_factory_switches_by_settings() -> None:
    s_ollama = Settings(_env_file=None, ai_provider="ollama")  # type: ignore[call-arg]
    assert get_llm_provider(s_ollama).name == "ollama"

    s_gemini = Settings(_env_file=None, ai_provider="gemini", gemini_api_key="AIzaSyValidFormatKey")  # type: ignore[call-arg]
    assert get_llm_provider(s_gemini).name == "gemini"

    s_openai = Settings(_env_file=None, ai_provider="openai", openai_api_key="sk-ValidFormatKey")  # type: ignore[call-arg]
    assert get_llm_provider(s_openai).name == "openai"

def test_regression_professional_summary_preserved_in_full_on_pdf_and_parse(client: TestClient) -> None:
    """Regression test: ensures multi-line professional summaries (> 95 chars) are never truncated."""
    headers = csrf_headers(client)
    expected_summary = (
        "Engenheira de Software Backend com 6 anos de experiência no desenvolvimento de APIs REST "
        "em Python e FastAPI, arquitetura de microsserviços e bancos de dados relacionais PostgreSQL."
    )
    pdf_bytes = _make_pdf_with_text(SAMPLE_RESUME_TEXT)

    r_up = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("curriculo_ana.pdf", pdf_bytes, "application/pdf")},
        headers=headers,
    )
    assert r_up.status_code == 200

    r_parse = client.post(
        "/api/v1/resumes/parse",
        json={"use_deterministic_only": True},
        headers=headers,
    )
    assert r_parse.status_code == 200
    parsed = r_parse.json()["data"]
    assert parsed["professional_summary"] == expected_summary
    assert parsed["summary_evidence_quote"] == expected_summary
    assert parsed["projects"][0]["description"].endswith("Python e FastAPI.")


@pytest.mark.asyncio
async def test_ollama_timeout_180s_preserves_error_handling_and_deterministic_fallback() -> None:
    """Verifies that timeout_seconds=180.0 converts ReadTimeout/ConnectError into AIUnavailableError and triggers deterministic fallback."""
    s = Settings(_env_file=None, ai_provider="ollama")  # type: ignore[call-arg]
    assert s.ai_timeout_seconds == 180.0

    def timeout_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Simulated 180s read timeout on CPU inference", request=req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as http:
        ollama = OllamaProvider(
            base_url="http://localhost:11434",
            timeout_seconds=s.ai_timeout_seconds,
            http_client=http,
        )
        with pytest.raises(AIUnavailableError) as exc_info:
            await ollama.enrich_resume_fast(SAMPLE_RESUME_TEXT, ParsedResumeData())
        assert "Ollama" in str(exc_info.value.message)
