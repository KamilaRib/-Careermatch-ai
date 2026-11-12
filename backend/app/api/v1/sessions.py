from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.config import Settings
from app.core.deps import get_app_settings
from app.core.logging import get_logger
from app.repositories.session_repository import SessionData
from app.schemas.common import SessionDeleted, SessionInfo
from app.security.session import get_session

router = APIRouter(prefix="/sessions", tags=["sessions"])
log = get_logger("app.sessions")


@router.get("/current", response_model=SessionInfo, summary="Inicializa/consulta a sessÃ£o anÃ´nima")
def current_session(
    _: SessionData = Depends(get_session), settings: Settings = Depends(get_app_settings)
) -> SessionInfo:
    return SessionInfo(active=True, ttl_minutes=settings.session_ttl_minutes)


@router.delete("/current", response_model=SessionDeleted, summary="Apaga todos os dados da sessÃ£o")
def delete_session(request: Request, session: SessionData = Depends(get_session)) -> SessionDeleted:
    repo = request.app.state.session_repo
    deleted = repo.delete(session.session_id)
    request.state.session_deleted = True
    log.info("session_deleted_by_user")
    return SessionDeleted(deleted=deleted)
