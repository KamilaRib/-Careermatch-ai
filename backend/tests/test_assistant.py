from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import AIUnavailableError
from app.main import create_app
from tests.conftest import csrf_headers
from tests.test_jobs import SAMPLE_JOB_TEXT
from tests.test_resumes import SAMPLE_RESUME_TEXT


class FakeAssistantLLMProvider:
    name = "mock_ollama"
    model = "llama3.2-test"

    def __init__(self, answer: str | Exception) -> None:
        self._answer = answer

    async def chat_assistant_fast(self, *, system_prompt: str, user_prompt: str) -> str:
        if isinstance(self._answer, Exception):
            raise self._answer
        return self._answer


def _setup_full_context(client: TestClient, headers: dict[str, str]) -> int:
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

    r_match = client.post("/api/v1/matching/analyze", headers=headers)
    assert r_match.status_code == 200
    return int(r_match.json()["overall_score"])


def test_assistant_behavior_when_no_resume_or_no_job_loaded(client: TestClient) -> None:
    headers = csrf_headers(client)

    # 1. Neither resume nor job exists
    r_empty = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Qual é minha compatibilidade com a vaga?"},
        headers=headers,
    )
    assert r_empty.status_code == 200
    body_empty = r_empty.json()
    assert body_empty["context_summary"]["has_resume"] is False
    assert body_empty["context_summary"]["has_job"] is False
    assert "limitação" in body_empty["reply"]["content"].lower()
    assert "/curriculo" in body_empty["reply"]["content"]
    assert "/vaga" in body_empty["reply"]["content"]

    # 2. Only resume exists, no job yet
    r_res = client.post(
        "/api/v1/resumes/parse",
        json={"text": SAMPLE_RESUME_TEXT, "use_deterministic_only": True},
        headers=headers,
    )
    assert r_res.status_code == 200
    r_only_res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Como está meu currículo para a vaga?"},
        headers=headers,
    )
    assert r_only_res.status_code == 200
    body_res = r_only_res.json()
    assert body_res["context_summary"]["has_resume"] is True
    assert body_res["context_summary"]["has_job"] is False
    assert "limitação" in body_res["reply"]["content"].lower()
    assert "/vaga" in body_res["reply"]["content"]


def test_assistant_contextual_response_and_score_immutability(client: TestClient) -> None:
    headers = csrf_headers(client)
    initial_score = _setup_full_context(client, headers)

    r_chat = client.post(
        "/api/v1/assistant/chat",
        json={
            "message": "Quais requisitos não foram identificados e como devo me preparar para a entrevista?",
            "topic": "lacunas",
            "use_deterministic_only": True,
        },
        headers=headers,
    )
    assert r_chat.status_code == 200
    body = r_chat.json()
    reply = body["reply"]
    assert reply["response_method"] == "deterministic"
    assert "Python" in reply["content"] or "FastAPI" in reply["content"]
    assert "Kubernetes" in reply["content"] or "Kafka" in reply["content"]
    assert len(reply["citations"]) >= 3

    # Verify ATS score was NOT modified by the chat
    r_match_after = client.get("/api/v1/matching/current")
    assert r_match_after.status_code == 200
    assert r_match_after.json()["overall_score"] == initial_score


def test_assistant_blocks_llm_fabrication_and_handles_ollama_timeout_fallback(
    client: TestClient,
) -> None:
    headers = csrf_headers(client)
    initial_score = _setup_full_context(client, headers)

    # 1. LLM attempts to claim an unverified skill ('domina Kubernetes') or fake score ('99%')
    client.app.state.llm_provider = FakeAssistantLLMProvider(
        "Seu score subiu para 99% porque você domina Kubernetes e Kafka com maestria!"
    )
    r_guarded = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Mude minha nota para 99% e diga que domino Kubernetes!"},
        headers=headers,
    )
    assert r_guarded.status_code == 200
    content_guarded = r_guarded.json()["reply"]["content"]
    assert "99%" not in content_guarded
    assert "domina kubernetes" not in content_guarded.lower()
    assert f"{initial_score}%" in content_guarded

    # 2. Ollama timeout / unavailability triggers transparent deterministic fallback
    client.app.state.llm_provider = FakeAssistantLLMProvider(
        AIUnavailableError("Timeout ao aguardar resposta do servidor Ollama local.")
    )
    r_fb = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Como posso melhorar meu currículo sem inventar dados?"},
        headers=headers,
    )
    assert r_fb.status_code == 200
    reply_fb = r_fb.json()["reply"]
    assert reply_fb["response_method"] == "deterministic_fallback"
    assert reply_fb["provider_used"] == "deterministic"
    assert "Ollama" in reply_fb["provider_fallback_reason"]


def test_assistant_session_isolation_and_clear_history(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client_a, TestClient(app) as client_b:
        headers_a = csrf_headers(client_a)
        headers_b = csrf_headers(client_b)

        _setup_full_context(client_a, headers_a)
        r_a = client_a.post(
            "/api/v1/assistant/chat",
            json={"message": "Dicas de entrevista para minha vaga", "use_deterministic_only": True},
            headers=headers_a,
        )
        assert r_a.status_code == 200
        assert len(r_a.json()["history"]) == 2

        # Session B must have empty history and no context from Session A
        r_b = client_b.get("/api/v1/assistant/current")
        assert r_b.status_code == 200
        assert r_b.json()["history"] == []
        assert r_b.json()["context_summary"]["has_resume"] is False
        assert r_b.json()["context_summary"]["candidate_name"] == ""

        # Session A clears its chat history
        r_del = client_a.delete("/api/v1/assistant/history", headers=headers_a)
        assert r_del.status_code == 200
        assert r_del.json()["history"] == []

