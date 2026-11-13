"""API v1 endpoints for resume upload, parsing, session retrieval and user confirmation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.core.config import Settings
from app.core.deps import get_app_settings
from app.core.errors import NotFoundError, ValidationFailed
from app.core.logging import get_logger
from app.repositories.session_repository import SessionData
from app.schemas.resume import (
    ResumeConfirmRequest,
    ResumeParseRequest,
    ResumeSessionState,
    ResumeUploadResponse,
)
from app.security.session import get_session
from app.security.upload_guard import validate_upload_file
from app.services.resume_parser import extract_text_from_upload, parse_resume_text
from app.ai.validators.evidence_validator import validate_resume_evidence

router = APIRouter(prefix="/resumes", tags=["resumes"])
log = get_logger("app.api.resumes")

SESSION_RESUME_KEY = "resume_state"


def _get_session_resume(session: SessionData) -> ResumeSessionState:
    existing = session.store.get(SESSION_RESUME_KEY)
    if isinstance(existing, ResumeSessionState):
        return existing
    if isinstance(existing, dict):
        return ResumeSessionState.model_validate(existing)
    state = ResumeSessionState()
    session.store[SESSION_RESUME_KEY] = state
    return state


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    summary="Faz upload seguro de currículo (PDF, DOCX, TXT) e extrai o texto em memória",
)
async def upload_resume(
    file: UploadFile = File(...),
    session: SessionData = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> ResumeUploadResponse:
    validated = await validate_upload_file(file, max_bytes=settings.max_upload_bytes)
    raw_text = await extract_text_from_upload(validated, max_chars=settings.max_text_chars)

    state = ResumeSessionState(
        has_resume=True,
        filename=validated.filename,
        source_kind=validated.kind,
        raw_text=raw_text,
        data=None,
        confirmed=False,
    )
    session.store[SESSION_RESUME_KEY] = state

    log.info(
        "resume_uploaded",
        extra={
            "kind": validated.kind,
            "size_bytes": validated.size_bytes,
            "char_count": len(raw_text),
        },
    )
    return ResumeUploadResponse(
        filename=validated.filename,
        kind=validated.kind,
        size_bytes=validated.size_bytes,
        char_count=len(raw_text),
        raw_text=raw_text,
    )


@router.post(
    "/parse",
    response_model=ResumeSessionState,
    summary="Estrutura o currículo da sessão (ou texto enviado) com IA ou fallback determinístico",
)
async def parse_resume(
    request: Request,
    payload: ResumeParseRequest | None = None,
    session: SessionData = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> ResumeSessionState:
    state = _get_session_resume(session)
    req = payload or ResumeParseRequest()

    if req.text:
        raw_text = req.text[: settings.max_text_chars]
        source_kind = state.source_kind if state.raw_text == raw_text and state.source_kind else "pasted"
        filename = state.filename if source_kind != "pasted" else None
    elif state.raw_text:
        raw_text = state.raw_text
        source_kind = state.source_kind or "pasted"
        filename = state.filename
    else:
        raise ValidationFailed(
            "Nenhum currículo enviado. Faça upload de um arquivo ou cole o texto do currículo.",
            code="missing_resume_text",
        )

    provider_override = getattr(request.app.state, "llm_provider", None)
    data, method, provider_used, fallback_reason, report = await parse_resume_text(
        raw_text,
        settings,
        provider=provider_override,
        use_deterministic_only=req.use_deterministic_only,
    )

    updated = ResumeSessionState(
        has_resume=True,
        filename=filename,
        source_kind=source_kind,
        raw_text=raw_text,
        data=data,
        extraction_method=method,
        provider_used=provider_used,
        provider_fallback_reason=fallback_reason,
        evidence_report=report,
        confirmed=False,
    )
    session.store[SESSION_RESUME_KEY] = updated
    log.info(
        "resume_parsed",
        extra={
            "method": method,
            "provider": provider_used,
            "verified_items": report.verified_items,
            "total_items": report.total_items_checked,
        },
    )
    return updated


@router.get(
    "/current",
    response_model=ResumeSessionState,
    summary="Retorna o currículo atual armazenado na sessão temporária",
)
def get_current_resume(session: SessionData = Depends(get_session)) -> ResumeSessionState:
    return _get_session_resume(session)


@router.put(
    "/current",
    response_model=ResumeSessionState,
    summary="Salva as edições revisadas e confirma os dados do currículo na sessão",
)
def update_current_resume(
    payload: ResumeConfirmRequest,
    session: SessionData = Depends(get_session),
) -> ResumeSessionState:
    state = _get_session_resume(session)
    if not state.has_resume or not state.raw_text:
        raise NotFoundError("Nenhum currículo ativo encontrado nesta sessão para confirmar.")

    report = validate_resume_evidence(state.raw_text, payload.data)
    updated = state.model_copy(
        update={
            "data": payload.data,
            "evidence_report": report,
            "confirmed": payload.confirmed,
        }
    )
    session.store[SESSION_RESUME_KEY] = updated
    log.info(
        "resume_confirmed",
        extra={
            "confirmed": payload.confirmed,
            "verified_items": report.verified_items,
            "total_items": report.total_items_checked,
        },
    )
    return updated
