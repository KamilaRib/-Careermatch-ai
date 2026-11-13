from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.errors import AIUnavailableError
from app.services.resume_parser import extract_text_from_upload
from tests.conftest import csrf_headers
from tests.test_jobs import SAMPLE_JOB_TEXT
from tests.test_resumes import SAMPLE_RESUME_TEXT


class FakeATSLLMProvider:
    name = "mock_ollama"
    model = "llama3.2-test"

    def __init__(self, summary_response: str | Exception) -> None:
        self._resp = summary_response

    async def enrich_ats_summary_fast(
        self,
        *,
        original_summary: str,
        job_title: str,
        verified_keywords: list[str],
    ) -> str:
        if isinstance(self._resp, Exception):
            raise self._resp
        return self._resp


def _prepare_confirmed_session(client: TestClient, headers: dict[str, str]) -> None:
    r_res = client.post(
        "/api/v1/resumes/parse",
        json={"text": SAMPLE_RESUME_TEXT, "use_deterministic_only": True},
        headers=headers,
    )
    assert r_res.status_code == 200
    client.put(
        "/api/v1/resumes/current",
        json={"data": r_res.json()["data"], "confirmed": True},
        headers=headers,
    )

    r_job = client.post(
        "/api/v1/jobs/parse",
        json={"text": SAMPLE_JOB_TEXT, "use_deterministic_only": True},
        headers=headers,
    )
    assert r_job.status_code == 200
    client.put(
        "/api/v1/jobs/current",
        json={"data": r_job.json()["data"], "confirmed": True},
        headers=headers,
    )


def test_ats_generate_requires_confirmed_resume_and_job(client: TestClient) -> None:
    headers = csrf_headers(client)
    r1 = client.post("/api/v1/ats-resume/generate", headers=headers)
    assert r1.status_code == 422
    assert r1.json()["error"]["code"] == "missing_resume"


def test_ats_generate_deterministic_and_zero_fabrication_and_readable_exports(
    client: TestClient,
) -> None:
    headers = csrf_headers(client)
    _prepare_confirmed_session(client, headers)

    # Generate ATS resume in deterministic mode
    r_gen = client.post(
        "/api/v1/ats-resume/generate",
        json={"use_deterministic_only": True},
        headers=headers,
    )
    assert r_gen.status_code == 200
    body = r_gen.json()
    assert body["optimization_method"] == "deterministic"
    assert body["approved"] is False
    assert body["preservation_report"]["zero_fabrication_verified"] is True
    assert len(body["changes"]) >= 1

    # Verify unverified job skills (Kubernetes, Kafka) are NEVER injected into technical_skills
    opt_skills = [s["name"].lower() for s in body["optimized_data"]["technical_skills"]]
    assert "python" in opt_skills
    assert "fastapi" in opt_skills
    assert "kubernetes" not in opt_skills
    assert "kafka" not in opt_skills

    # Unverified skills appear ONLY in suggested_keywords as advisory items
    sugg_names = [s["keyword"].lower() for s in body["suggested_keywords"]]
    assert any("kubernetes" in s or "kafka" in s for s in sugg_names)

    # Exporting before human approval must be blocked with 422
    r_exp_blocked = client.get("/api/v1/ats-resume/export/pdf")
    assert r_exp_blocked.status_code == 422
    assert r_exp_blocked.json()["error"]["code"] == "ats_resume_not_approved"

    # Human edits & approves the ATS resume
    opt_data = body["optimized_data"]
    r_approve = client.put(
        "/api/v1/ats-resume/current",
        json={"optimized_data": opt_data, "approved": True},
        headers=headers,
    )
    assert r_approve.status_code == 200
    assert r_approve.json()["approved"] is True

    # Export PDF and verify text extractability using /api/v1/resumes/upload
    r_pdf = client.get("/api/v1/ats-resume/export/pdf")
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    r_up_pdf = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("curriculo-ats.pdf", r_pdf.content, "application/pdf")},
        headers=headers,
    )
    assert r_up_pdf.status_code == 200
    pdf_text = r_up_pdf.json()["raw_text"]
    assert "Ana Carolina Mendes" in pdf_text
    assert "RESUMO PROFISSIONAL" in pdf_text
    assert "FastAPI" in pdf_text

    # Export DOCX and verify text extractability using /api/v1/resumes/upload
    r_docx = client.get("/api/v1/ats-resume/export/docx")
    assert r_docx.status_code == 200
    assert "wordprocessingml" in r_docx.headers["content-type"]
    r_up_docx = client.post(
        "/api/v1/resumes/upload",
        files={
            "file": (
                "curriculo-ats.docx",
                r_docx.content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=headers,
    )
    assert r_up_docx.status_code == 200
    docx_text = r_up_docx.json()["raw_text"]
    assert "Ana Carolina Mendes" in docx_text
    assert "RESUMO PROFISSIONAL" in docx_text
    assert "PostgreSQL" in docx_text


def test_ats_generate_blocks_llm_fabrication_and_handles_ollama_fallback(
    client: TestClient,
) -> None:
    headers = csrf_headers(client)
    _prepare_confirmed_session(client, headers)

    # 1. LLM attempts to hallucinate 'Kafka' (an unverified job requirement) into the summary
    client.app.state.llm_provider = FakeATSLLMProvider(
        "Engenheira Backend com 6 anos em Python, FastAPI e mensageria Kafka em produção."
    )
    r_hallucinated = client.post("/api/v1/ats-resume/generate", json={}, headers=headers)
    assert r_hallucinated.status_code == 200
    body_h = r_hallucinated.json()
    assert "kafka" not in body_h["optimized_data"]["professional_summary"].lower()
    assert len(body_h["preservation_report"]["blocked_fabrications"]) >= 1

    # 2. Ollama unavailable -> falls back to deterministic transparently
    client.app.state.llm_provider = FakeATSLLMProvider(
        AIUnavailableError("Ollama offline durante geração ATS.")
    )
    r_fb = client.post("/api/v1/ats-resume/generate", json={}, headers=headers)
    assert r_fb.status_code == 200
    body_fb = r_fb.json()
    assert body_fb["optimization_method"] == "deterministic_fallback"
    assert body_fb["provider_used"] == "deterministic"
    assert "Ollama" in body_fb["provider_fallback_reason"]
