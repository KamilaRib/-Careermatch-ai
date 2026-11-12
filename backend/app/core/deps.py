"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from app.core.config import Settings


def get_app_settings(request: Request) -> Settings:
    """Settings bound to the running app instance (supports per-app overrides in tests)."""
    return request.app.state.settings
