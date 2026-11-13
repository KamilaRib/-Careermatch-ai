from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.core.config import Settings
from app.core.deps import get_app_settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health(settings: Settings = Depends(get_app_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.app_env,
        ai_provider=settings.ai_provider,
        ai_configured=settings.ai_configured,
        ai_key_warning=settings.ai_key_warning,
    )
