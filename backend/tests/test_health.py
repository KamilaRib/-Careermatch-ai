from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings


def test_health_ok(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"
    assert body["ai_provider"] == "ollama"
    assert body["ai_configured"] is True
    # Never leak keys
    sanitized = str(body).lower().replace("ai_configured", "").replace("ai_key_warning", "")
    assert "key" not in sanitized


def test_security_headers(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "x-request-id" in r.headers


def test_openapi_available_and_utf8_clean(client: TestClient) -> None:
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert "/api/v1/health" in spec["paths"]
    raw_spec = r.text
    assert "sessão anônima" in raw_spec
    assert "Ã" not in raw_spec


def test_unknown_route_returns_json_error(client: TestClient) -> None:
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "http_error"


def test_cors_restricted(client: TestClient) -> None:
    ok = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert bad.headers.get("access-control-allow-origin") is None


def test_production_requires_api_key_for_cloud_providers() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="production", ai_provider="gemini", gemini_api_key="")  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="production", ai_provider="openai", openai_api_key="")  # type: ignore[call-arg]
    # Ollama works in production without a paid API key
    s_ollama = Settings(_env_file=None, app_env="production", ai_provider="ollama")  # type: ignore[call-arg]
    assert s_ollama.ai_configured is True


def test_api_key_not_in_repr() -> None:
    s = Settings(_env_file=None, gemini_api_key="super-secret-value")  # type: ignore[call-arg]
    assert "super-secret-value" not in repr(s)
