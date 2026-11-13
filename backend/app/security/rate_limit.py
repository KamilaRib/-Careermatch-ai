"""Simple sliding-window in-memory rate limiter (per client IP + bucket)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

# Paths that call LLMs get a stricter bucket.
AI_PATH_PREFIXES = (
    "/api/v1/resumes/parse",
    "/api/v1/resumes/optimize",
    "/api/v1/ats-resume/generate",
    "/api/v1/jobs/parse",
    "/api/v1/jobs/extract-url",
    "/api/v1/matching/analyze",
    "/api/v1/assistant/chat",
)


class RateLimiter:
    def __init__(self, clock=time.monotonic) -> None:  # type: ignore[no-untyped-def]
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._clock = clock

    def allow(self, key: str, limit: int, window: float = 60.0) -> tuple[bool, int]:
        now = self._clock()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                retry = int(window - (now - q[0])) + 1
                return False, retry
            q.append(now)
            if len(self._hits) > 50_000:  # bound memory
                for k in [k for k, v in self._hits.items() if not v][:10_000]:
                    self._hits.pop(k, None)
            return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter, general: int, ai: int) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.limiter = limiter
        self.general = general
        self.ai = ai

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if not path.startswith("/api/") or request.method == "OPTIONS":
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        is_ai = path.startswith(AI_PATH_PREFIXES)
        bucket, limit = ("ai", self.ai) if is_ai else ("general", self.general)
        ok, retry = self.limiter.allow(f"{bucket}:{ip}", limit)
        if not ok:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry)},
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Muitas requisições. Aguarde alguns instantes.",
                    }
                },
            )
        return await call_next(request)
