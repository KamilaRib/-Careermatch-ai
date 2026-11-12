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
    assert body["ai_configured"] is False
    # Never leak keys
    assert "key" not in str(body).lower().replace("ai_configured", "")


def test_security_headers(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "x-request-id" in r.headers


def test_openapi_available(client: TestClient) -> None:
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/health" in r.json()["paths"]


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


def test_production_requires_api_key() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="production", gemini_api_key="")  # type: ignore[call-arg]


def test_api_key_not_in_repr() -> None:
    s = Settings(_env_file=None, gemini_api_key="super-secret-value")  # type: ignore[call-arg]
    assert "super-secret-value" not in repr(s)
