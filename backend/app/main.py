"""FastAPI application factory for CareerMatch AI."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.observability import RequestLoggingMiddleware
from app.repositories.session_repository import InMemorySessionRepository, run_periodic_cleanup
from app.security.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.security.rate_limit import RateLimiter, RateLimitMiddleware
from app.security.session import CSRF_HEADER, SessionMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    log = get_logger("app")

    repo = InMemorySessionRepository(ttl_seconds=settings.session_ttl_minutes * 60)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        log.info(
            "startup",
            extra={
                "env": settings.app_env,
                "ai_provider": settings.ai_provider,
                "ai_configured": settings.ai_configured,
            },
        )
        if not settings.ai_configured:
            log.warning("ai_key_missing", extra={"ai_provider": settings.ai_provider})
        task = asyncio.create_task(
            run_periodic_cleanup(repo, settings.session_cleanup_interval_seconds)
        )
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            log.info("shutdown")

    app = FastAPI(
        title="CareerMatch AI API",
        version=__version__,
        description="API de matchmaking entre currículos e vagas com IA. Sem login; sessões anônimas temporárias.",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.session_repo = repo
    app.state.rate_limiter = RateLimiter()

    # Middleware order: last added = outermost.
    app.add_middleware(SessionMiddleware, repo=repo, settings=settings)
    app.add_middleware(
        RateLimitMiddleware,
        limiter=app.state.rate_limiter,
        general=settings.rate_limit_per_minute,
        ai=settings.rate_limit_ai_per_minute,
    )
    # Upload limit + small margin for multipart overhead.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_upload_bytes + 64 * 1024)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", CSRF_HEADER],
        expose_headers=["X-Request-ID", "Content-Disposition"],
        max_age=600,
    )
    app.add_middleware(RequestLoggingMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
