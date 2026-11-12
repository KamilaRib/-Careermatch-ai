"""Anonymous, isolated sessions via HttpOnly cookie + CSRF double-submit token.

- Session id: 256-bit random (`secrets.token_urlsafe(32)`), HttpOnly, SameSite=Lax,
  Secure in production.
- CSRF token: random, readable cookie (`cm_csrf`) that the SPA echoes back in the
  `X-CSRF-Token` header on every state-changing request. Compared in constant time
  against the token stored server-side for that session.
"""

from __future__ import annotations

import hmac
import secrets

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.repositories.session_repository import SessionData, SessionRepository

SESSION_COOKIE = "cm_session"
CSRF_COOKIE = "cm_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_EXEMPT_PATHS = {"/api/v1/health"}


def new_token() -> str:
    return secrets.token_urlsafe(32)


class SessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, repo: SessionRepository, settings: Settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.repo = repo
        self.settings = settings

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        sid = request.cookies.get(SESSION_COOKIE)
        session: SessionData | None = self.repo.get(sid) if sid else None
        is_new = session is None

        if request.method not in SAFE_METHODS and request.url.path not in CSRF_EXEMPT_PATHS:
            # State-changing requests require an existing session and a valid CSRF token.
            header = request.headers.get(CSRF_HEADER, "")
            if session is None or not header or not hmac.compare_digest(header, session.csrf_token):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "csrf_failed",
                            "message": "Sessão inválida ou expirada. Recarregue a página.",
                        }
                    },
                )

        if session is None:
            session = self.repo.create(new_token(), new_token())
        else:
            self.repo.touch(session.session_id)

        request.state.session = session
        response = await call_next(request)

        # The session may have been deleted by the handler (DELETE /sessions/current).
        if getattr(request.state, "session_deleted", False):
            response.delete_cookie(SESSION_COOKIE, path="/")
            response.delete_cookie(CSRF_COOKIE, path="/")
            return response

        if is_new or request.cookies.get(CSRF_COOKIE) != session.csrf_token:
            self._set_cookies(response, session)
        return response

    def _set_cookies(self, response: Response, session: SessionData) -> None:
        max_age = self.settings.session_ttl_minutes * 60
        secure = self.settings.is_production
        response.set_cookie(
            SESSION_COOKIE, session.session_id, max_age=max_age, httponly=True,
            secure=secure, samesite="lax", path="/",
        )
        response.set_cookie(
            CSRF_COOKIE, session.csrf_token, max_age=max_age, httponly=False,
            secure=secure, samesite="lax", path="/",
        )


def get_session(request: Request) -> SessionData:
    """FastAPI dependency returning the current isolated session."""
    return request.state.session
