from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.security.ssrf_guard import (
    ExternalFetchError,
    SSRFBlockedError,
    fetch_public_job_url_text,
    is_ip_public_and_safe,
    validate_public_url,
)
from tests.conftest import csrf_headers

SAMPLE_JOB_TEXT = """Engenheiro(a) de Software Backend Sênior | FinPay Tecnologia
Localização: São Paulo - SP | Modelo: Híbrido

Responsabilidades
- Projetar e manter APIs REST de alta disponibilidade utilizando Python e FastAPI.
- Modelar bancos de dados relacionais em PostgreSQL e otimizar consultas críticas.
- Trabalhar em equipe com times de produto e segurança.

Requisitos Obrigatórios
- 5 anos de experiência em desenvolvimento de software backend.
- Domínio de Python e FastAPI.
- Experiência sólida com PostgreSQL e Docker.
- Bacharelado em Ciência da Computação ou área correlata.
- Inglês avançado (imprescindível).

Requisitos Desejáveis
- Conhecimento em Kubernetes e AWS.
- Experiência com mensageria Kafka.
"""


@pytest.mark.parametrize(
    "blocked_url",
    [
        "http://127.0.0.1:8000/api/v1/health",
        "http://localhost/admin",
        "http://10.0.0.1/internal",
        "http://172.16.5.4/secret",
        "http://192.168.1.10/router",
        "http://169.254.169.254/latest/meta-data/",
        "http://100.100.100.200/latest/meta-data/",
        "http://[::1]/loopback",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://service.internal/vaga",
        "file:///etc/passwd",
        "ftp://ftp.example.com/vaga.txt",
        "http://user:pass@example.com/vaga",
    ],
)
def test_ssrf_guard_blocks_private_local_metadata_and_bad_schemes(blocked_url: str) -> None:
    with pytest.raises(SSRFBlockedError):
        validate_public_url(blocked_url, resolver=lambda h, p: ["93.184.216.34"])


def test_ssrf_guard_blocks_domain_resolving_to_private_ip() -> None:
    with pytest.raises(SSRFBlockedError):
        validate_public_url(
            "https://vagas.empresa-externa.com/job/123",
            resolver=lambda h, p: ["10.24.0.12"],
        )


def test_ssrf_guard_allows_public_ip_and_blocks_cgnat() -> None:
    assert is_ip_public_and_safe("93.184.216.34") is True
    assert is_ip_public_and_safe("100.64.1.1") is False
    assert is_ip_public_and_safe("::ffff:127.0.0.1") is False


@pytest.mark.asyncio
async def test_ssrf_guard_blocks_unsafe_redirect_to_internal_ip() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SSRFBlockedError):
            await fetch_public_job_url_text(
                "https://jobs.example.com/vaga",
                resolver=lambda h, p: ["93.184.216.34"],
                http_client=http,
            )


@pytest.mark.asyncio
async def test_ssrf_guard_rejects_captcha_or_login_wall_without_bypass() -> None:
    html_captcha = "<html><body><div>Verify you are human</div><div class='cf-turnstile'></div></body></html>"

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Type": "text/html"}, text=html_captcha)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ExternalFetchError) as exc:
            await fetch_public_job_url_text(
                "https://jobs.example.com/protected",
                resolver=lambda h, p: ["93.184.216.34"],
                http_client=http,
            )
        assert "cole a descrição" in exc.value.message.lower()


def test_parse_job_deterministic_extracts_seniority_model_and_classified_requirements(
    client: TestClient,
) -> None:
    headers = csrf_headers(client)
    r = client.post(
        "/api/v1/jobs/parse",
        json={"text": SAMPLE_JOB_TEXT, "use_deterministic_only": True},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["has_job"] is True
    assert body["extraction_method"] == "deterministic_fallback"
    assert body["confirmed"] is False

    data = body["data"]
    assert data["title"] == "Engenheiro(a) de Software Backend Sênior"
    assert data["company"] == "FinPay Tecnologia"
    assert data["seniority"] == "Sênior"
    assert data["work_model"] == "Híbrido"
    assert len(data["responsibilities"]) == 3

    reqs = data["requirements"]
    assert any(req["importance"] == "obrigatorio" and "Python" in req["name"] for req in reqs)
    assert any(req["importance"] == "desejavel" and "Kubernetes" in req["name"] for req in reqs)
    assert any(req["is_eliminatory"] is True and "Inglês" in req["name"] for req in reqs)
    assert body["evidence_report"]["unverified_warnings"] == []


def test_extract_url_endpoint_and_session_isolation(settings: Settings) -> None:
    app = create_app(settings)
    html_page = f"<html><body><h1>Vaga</h1><p>{SAMPLE_JOB_TEXT}</p></body></html>"

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Type": "text/html"}, text=html_page)

    with TestClient(app) as client_a, TestClient(app) as client_b:
        app.state.ssrf_resolver = lambda h, p: ["93.184.216.34"]
        app.state.ssrf_http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        headers_a = csrf_headers(client_a)
        headers_b = csrf_headers(client_b)

        r_url = client_a.post(
            "/api/v1/jobs/extract-url",
            json={"url": "https://careers.finpay.example.com/backend-sr", "use_deterministic_only": True},
            headers=headers_a,
        )
        assert r_url.status_code == 200
        job_data = r_url.json()["data"]
        assert job_data["company"] == "FinPay Tecnologia"

        # Client B must NOT see Client A's job
        r_b = client_b.get("/api/v1/jobs/current")
        assert r_b.status_code == 200
        assert r_b.json()["has_job"] is False

        # Client A confirms job requirements
        r_confirm = client_a.put(
            "/api/v1/jobs/current",
            json={"data": job_data, "confirmed": True},
            headers=headers_a,
        )
        assert r_confirm.status_code == 200
        assert r_confirm.json()["confirmed"] is True

        # SSRF attempt via endpoint returns 403
        r_ssrf = client_a.post(
            "/api/v1/jobs/extract-url",
            json={"url": "http://127.0.0.1:8000/api/v1/health"},
            headers=headers_a,
        )
        assert r_ssrf.status_code == 403
        assert r_ssrf.json()["error"]["code"] == "ssrf_blocked"
