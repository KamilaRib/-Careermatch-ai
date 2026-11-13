"""API v1 endpoints for job description parsing, safe URL extraction and user confirmation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.config import Settings
from app.core.deps import get_app_settings
from app.core.logging import get_logger
from app.repositories.session_repository import SessionData
from app.schemas.job import (
    JobConfirmRequest,
    JobExtractUrlRequest,
    JobParseRequest,
    JobSessionState,
)
from app.security.session import get_session
from app.security.ssrf_guard import fetch_public_job_url_text
from app.services.job_parser import parse_job_text, validate_job_evidence

router = APIRouter(prefix="/jobs", tags=["jobs"])
log = get_logger("app.api.jobs")

SESSION_JOB_KEY = "job_state"


def get_session_job(session: SessionData) -> JobSessionState:
    existing = session.store.get(SESSION_JOB_KEY)
    if isinstance(existing, JobSessionState):
        return existing
    if isinstance(existing, dict):
        return JobSessionState.model_validate(existing)
    state = JobSessionState()
    session.store[SESSION_JOB_KEY] = state
    return state


@router.post(
    "/parse",
    response_model=JobSessionState,
    summary="Analisa e estrutura a descrição da vaga com IA ou fallback determinístico",
)
async def parse_job_endpoint(
    request: Request,
    payload: JobParseRequest,
    session: SessionData = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> JobSessionState:
    raw_text = payload.text[: settings.max_text_chars]
    provider_override = getattr(request.app.state, "job_llm_provider", None) or getattr(
        request.app.state, "llm_provider", None
    )

    data, method, provider_used, fallback_reason, report = await parse_job_text(
        raw_text,
        settings,
        provider=provider_override,
        use_deterministic_only=payload.use_deterministic_only,
    )

    state = JobSessionState(
        has_job=True,
        source_kind="pasted",
        source_url=None,
        raw_text=raw_text,
        data=data,
        extraction_method=method,
        provider_used=provider_used,
        provider_fallback_reason=fallback_reason,
        evidence_report=report,
        confirmed=False,
    )
    session.store[SESSION_JOB_KEY] = state
    log.info(
        "job_parsed",
        extra={
            "method": method,
            "provider": provider_used,
            "requirements_count": len(data.requirements),
        },
    )
    return state


@router.post(
    "/extract-url",
    response_model=JobSessionState,
    summary="Extrai o texto de uma URL pública de vaga com proteção SSRF e analisa os requisitos",
)
async def extract_job_url_endpoint(
    request: Request,
    payload: JobExtractUrlRequest,
    session: SessionData = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> JobSessionState:
    resolver_override = getattr(request.app.state, "ssrf_resolver", None)
    http_override = getattr(request.app.state, "ssrf_http_client", None)

    extracted_text = await fetch_public_job_url_text(
        payload.url,
        resolver=resolver_override,
        http_client=http_override,
    )
    raw_text = extracted_text[: settings.max_text_chars]

    if not payload.parse_immediately:
        state = JobSessionState(
            has_job=True,
            source_kind="url",
            source_url=payload.url,
            raw_text=raw_text,
            data=None,
            confirmed=False,
        )
        session.store[SESSION_JOB_KEY] = state
        return state

    provider_override = getattr(request.app.state, "job_llm_provider", None) or getattr(
        request.app.state, "llm_provider", None
    )
    data, method, provider_used, fallback_reason, report = await parse_job_text(
        raw_text,
        settings,
        provider=provider_override,
        use_deterministic_only=payload.use_deterministic_only,
    )

    state = JobSessionState(
        has_job=True,
        source_kind="url",
        source_url=payload.url,
        raw_text=raw_text,
        data=data,
        extraction_method=method,
        provider_used=provider_used,
        provider_fallback_reason=fallback_reason,
        evidence_report=report,
        confirmed=False,
    )
    session.store[SESSION_JOB_KEY] = state
    log.info(
        "job_extracted_from_url",
        extra={
            "method": method,
            "requirements_count": len(data.requirements),
        },
    )
    return state


@router.get(
    "/current",
    response_model=JobSessionState,
    summary="Retorna a vaga atual armazenada na sessão temporária",
)
def get_current_job(session: SessionData = Depends(get_session)) -> JobSessionState:
    return get_session_job(session)


@router.put(
    "/current",
    response_model=JobSessionState,
    summary="Salva preenchimento manual ou confirma os requisitos revisados da vaga na sessão",
)
def update_current_job(
    payload: JobConfirmRequest,
    session: SessionData = Depends(get_session),
) -> JobSessionState:
    existing = get_session_job(session)
    raw_text = (payload.raw_text or existing.raw_text or "").strip()
    if not raw_text:
        # Build synthetic reference text from manual entry so evidence remains consistent
        req_lines = [r.name for r in payload.data.requirements if r.name]
        raw_text = "\n".join(
            [
                f"{payload.data.title} | {payload.data.company}",
                *payload.data.responsibilities,
                *req_lines,
            ]
        ).strip()

    report = validate_job_evidence(raw_text, payload.data)
    updated = JobSessionState(
        has_job=True,
        source_kind=existing.source_kind or "manual",
        source_url=existing.source_url,
        raw_text=raw_text,
        data=payload.data,
        extraction_method=existing.extraction_method or "deterministic_fallback",
        provider_used=existing.provider_used or "manual",
        provider_fallback_reason=existing.provider_fallback_reason,
        evidence_report=report,
        confirmed=payload.confirmed,
    )
    session.store[SESSION_JOB_KEY] = updated
    log.info(
        "job_confirmed",
        extra={
            "confirmed": payload.confirmed,
            "requirements_count": len(payload.data.requirements),
        },
    )
    return updated
