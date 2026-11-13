"""REST endpoints for Phase 5 — ATS-Friendly Resume Generation, Review & Export."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request, Response

from app.api.v1.jobs import get_session_job
from app.api.v1.matching import SESSION_MATCHING_KEY
from app.api.v1.resumes import _get_session_resume
from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationFailed
from app.core.logging import get_logger
from app.repositories.session_repository import SessionData
from app.schemas.ats_resume import (
    ATSResumeGenerateRequest,
    ATSResumeResult,
    ATSResumeUpdateRequest,
    CurrentATSResumeResponse,
)
from app.schemas.job import ParsedJobData
from app.schemas.matching import MatchingResult
from app.schemas.resume import ParsedResumeData
from app.security.session import get_session
from app.services.ats_generator import (
    export_ats_resume_docx,
    export_ats_resume_pdf,
    generate_ats_resume,
    render_ats_markdown,
    render_ats_plain_text,
)
from app.services.matching_engine import calculate_matching

router = APIRouter(prefix="/ats-resume", tags=["ats-resume"])
log = get_logger("app.api.ats_resume")

SESSION_ATS_RESUME_KEY = "ats_resume_result"


def _require_confirmed_resume_and_job(
    session: SessionData,
) -> tuple[ParsedResumeData, ParsedJobData, MatchingResult, str]:
    resume_state = _get_session_resume(session)
    job_state = get_session_job(session)

    if not resume_state.has_resume or resume_state.data is None:
        raise ValidationFailed(
            "Nenhum currículo estruturado encontrado na sessão. Conclua a etapa '/curriculo' primeiro.",
            code="missing_resume",
        )
    if not resume_state.confirmed:
        raise ValidationFailed(
            "Os dados do currículo precisam ser revisados e confirmados antes da geração ATS.",
            code="resume_not_confirmed",
        )

    if not job_state.has_job or job_state.data is None:
        raise ValidationFailed(
            "Nenhuma vaga estruturada encontrado na sessão. Conclua a etapa '/vaga' primeiro.",
            code="missing_job",
        )
    if not job_state.confirmed:
        raise ValidationFailed(
            "Os requisitos da vaga precisam ser revisados e confirmados antes da geração ATS.",
            code="job_not_confirmed",
        )

    raw_resume_text = resume_state.raw_text or ""
    existing_matching = session.store.get(SESSION_MATCHING_KEY)
    if isinstance(existing_matching, MatchingResult):
        matching = existing_matching
    elif isinstance(existing_matching, dict):
        matching = MatchingResult.model_validate(existing_matching)
    else:
        matching = calculate_matching(
            resume=resume_state.data,
            job=job_state.data,
            raw_resume_text=raw_resume_text,
        )
        session.store[SESSION_MATCHING_KEY] = matching

    return resume_state.data, job_state.data, matching, raw_resume_text


@router.post(
    "/generate",
    response_model=ATSResumeResult,
    summary="Gera uma versão otimizada e compatível com ATS do currículo confirmado para a vaga confirmada",
)
async def generate_ats_resume_endpoint(
    request: Request,
    payload: ATSResumeGenerateRequest | None = None,
    session: SessionData = Depends(get_session),
) -> ATSResumeResult:
    resume, job, matching, raw_resume_text = _require_confirmed_resume_and_job(session)
    req = payload or ATSResumeGenerateRequest()
    settings: Settings = request.app.state.settings
    provider_override = getattr(request.app.state, "llm_provider", None)

    result = await generate_ats_resume(
        original_resume=resume,
        job=job,
        matching=matching,
        raw_resume_text=raw_resume_text,
        settings=settings,
        use_deterministic_only=req.use_deterministic_only,
        provider=provider_override,
    )

    session.store[SESSION_ATS_RESUME_KEY] = result
    log.info(
        "ats_resume_generated",
        extra={
            "method": result.optimization_method,
            "provider": result.provider_used,
            "changes_count": len(result.changes),
            "incorporated_keywords_count": len(result.incorporated_keywords),
        },
    )
    return result


@router.get(
    "/current",
    response_model=CurrentATSResumeResponse,
    summary="Retorna o currículo ATS otimizado atual da sessão",
)
async def get_current_ats_resume_endpoint(
    session: SessionData = Depends(get_session),
) -> CurrentATSResumeResponse:
    raw = session.store.get(SESSION_ATS_RESUME_KEY)
    if raw is None:
        return CurrentATSResumeResponse(has_ats_resume=False, result=None)
    result = raw if isinstance(raw, ATSResumeResult) else ATSResumeResult.model_validate(raw)
    return CurrentATSResumeResponse(has_ats_resume=True, result=result)


@router.put(
    "/current",
    response_model=ATSResumeResult,
    summary="Atualiza e aprova o currículo ATS otimizado antes da exportação",
)
async def update_and_approve_ats_resume_endpoint(
    payload: ATSResumeUpdateRequest,
    session: SessionData = Depends(get_session),
) -> ATSResumeResult:
    raw = session.store.get(SESSION_ATS_RESUME_KEY)
    if isinstance(raw, ATSResumeResult):
        existing = raw.model_copy(deep=True)
    elif isinstance(raw, dict):
        existing = ATSResumeResult.model_validate(raw)
    else:
        existing = ATSResumeResult(optimized_data=payload.optimized_data)

    updated_data = payload.optimized_data
    existing.optimized_data = updated_data
    existing.markdown_preview = render_ats_markdown(updated_data)
    existing.plain_text_preview = render_ats_plain_text(updated_data)
    existing.approved = payload.approved

    session.store[SESSION_ATS_RESUME_KEY] = existing
    log.info(
        "ats_resume_updated",
        extra={
            "approved": existing.approved,
            "skills_count": len(updated_data.technical_skills),
        },
    )
    return existing


@router.get(
    "/export/{fmt}",
    summary="Exporta o currículo ATS aprovado em PDF, DOCX, TXT ou Markdown",
)
async def export_ats_resume_endpoint(
    fmt: Literal["pdf", "docx", "txt", "md"],
    session: SessionData = Depends(get_session),
) -> Response:
    raw = session.store.get(SESSION_ATS_RESUME_KEY)
    if raw is None:
        raise NotFoundError(
            "Nenhum currículo ATS gerado nesta sessão. Gere o currículo antes de exportar.",
            code="ats_resume_not_found",
        )
    result = raw if isinstance(raw, ATSResumeResult) else ATSResumeResult.model_validate(raw)
    if not result.approved:
        raise ValidationFailed(
            "Revise e aprove o currículo otimizado ('Aprovar para exportação') antes de baixar o arquivo.",
            code="ats_resume_not_approved",
        )

    if fmt == "pdf":
        pdf_bytes = export_ats_resume_pdf(result.optimized_data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="curriculo-ats.pdf"'},
        )
    if fmt == "docx":
        docx_bytes = export_ats_resume_docx(result.optimized_data)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": 'attachment; filename="curriculo-ats.docx"'},
        )
    if fmt == "txt":
        txt_bytes = result.plain_text_preview.encode("utf-8")
        return Response(
            content=txt_bytes,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="curriculo-ats.txt"'},
        )

    md_bytes = result.markdown_preview.encode("utf-8")
    return Response(
        content=md_bytes,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="curriculo-ats.md"'},
    )
