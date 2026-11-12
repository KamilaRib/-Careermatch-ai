from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        frontend_url="http://localhost:5173",
        gemini_api_key="",
        openai_api_key="",
        rate_limit_per_minute=1000,
        rate_limit_ai_per_minute=1000,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def csrf_headers(client: TestClient) -> dict[str, str]:
    """Bootstrap a session and return headers with a valid CSRF token."""
    r = client.get("/api/v1/sessions/current")
    assert r.status_code == 200
    return {"X-CSRF-Token": client.cookies.get("cm_csrf")}
