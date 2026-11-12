from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.session_repository import InMemorySessionRepository
from app.security.rate_limit import RateLimiter
from tests.conftest import csrf_headers


def test_session_cookie_is_httponly_and_random(client: TestClient) -> None:
    r = client.get("/api/v1/sessions/current")
    set_cookie = ",".join(r.headers.get_list("set-cookie"))
    assert "cm_session=" in set_cookie
    assert "HttpOnly" in set_cookie.split("cm_csrf=")[0] or "httponly" in set_cookie.lower()
    sid = client.cookies.get("cm_session")
    assert sid and len(sid) >= 40


def test_two_clients_get_isolated_sessions(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as a, TestClient(app) as b:
        a.get("/api/v1/sessions/current")
        b.get("/api/v1/sessions/current")
        assert a.cookies.get("cm_session") != b.cookies.get("cm_session")
        repo = app.state.session_repo
        sa = repo.get(a.cookies.get("cm_session"))
        sb = repo.get(b.cookies.get("cm_session"))
        sa.store["resume"] = "A"
        assert "resume" not in sb.store


def test_post_without_csrf_is_rejected(client: TestClient) -> None:
    client.get("/api/v1/sessions/current")
    r = client.delete("/api/v1/sessions/current")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"


def test_post_with_wrong_csrf_is_rejected(client: TestClient) -> None:
    client.get("/api/v1/sessions/current")
    r = client.delete("/api/v1/sessions/current", headers={"X-CSRF-Token": "wrong"})
    assert r.status_code == 403


def test_delete_session_clears_data(client: TestClient) -> None:
    headers = csrf_headers(client)
    sid = client.cookies.get("cm_session")
    repo = client.app.state.session_repo
    repo.get(sid).store["resume"] = "dados"
    r = client.delete("/api/v1/sessions/current", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    assert repo.get(sid) is None


def test_repository_ttl_expiration() -> None:
    now = [0.0]
    repo = InMemorySessionRepository(ttl_seconds=10, clock=lambda: now[0])
    repo.create("s1", "c1")
    repo.create("s2", "c2")
    now[0] = 5
    repo.touch("s2")
    now[0] = 12
    assert repo.get("s1") is None  # expired
    assert repo.get("s2") is not None  # sliding expiration
    now[0] = 30
    assert repo.purge_expired() == 1
    assert repo.count() == 0


def test_rate_limiter() -> None:
    now = [0.0]
    rl = RateLimiter(clock=lambda: now[0])
    assert rl.allow("k", 2)[0]
    assert rl.allow("k", 2)[0]
    ok, retry = rl.allow("k", 2)
    assert not ok and retry > 0
    now[0] = 61
    assert rl.allow("k", 2)[0]


def test_rate_limit_middleware_returns_429(settings: Settings) -> None:
    s = settings.model_copy(update={"rate_limit_per_minute": 2})
    app = create_app(s)
    with TestClient(app) as c:
        assert c.get("/api/v1/health").status_code == 200
        assert c.get("/api/v1/health").status_code == 200
        r = c.get("/api/v1/health")
        assert r.status_code == 429
        assert "retry-after" in r.headers


def test_payload_too_large(client: TestClient) -> None:
    headers = csrf_headers(client)
    big = b"x" * (11 * 1024 * 1024)
    r = client.post("/api/v1/sessions/current", content=big, headers=headers)
    assert r.status_code == 413
