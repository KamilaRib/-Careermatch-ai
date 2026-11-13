"""API v1 endpoints for deterministic ATS matchmaking between session resume and job."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.jobs import get_session_job
from app.api.v1.resumes import _get_session_resume
from app.core.errors import ValidationFailed
from app.core.logging import get_logger
from app.repositories.session_repository import SessionData
from app.schemas.matching import MatchingResult
from app.security.session import get_session
from app.services.matching_engine import calculate_matching

router = APIRouter(prefix="/matching", tags=["matching"])
log = get_logger("app.api.matching")

SESSION_MATCHING_KEY = "matching_result"


@router.post(
    "/analyze",
    response_model=MatchingResult,
    summary="Calcula o score determinístico de compatibilidade entre o currículo e a vaga da sessão",
)
def analyze_matching(session: SessionData = Depends(get_session)) -> MatchingResult:
    resume_state = _get_session_resume(session)
    job_state = get_session_job(session)

    if not resume_state.has_resume or resume_state.data is None:
        raise ValidationFailed(
            "Envie e estruture seu currículo antes de calcular a compatibilidade.",
            code="missing_resume",
        )
    if not resume_state.confirmed:
        raise ValidationFailed(
            "Confirme os dados revisados do seu currículo antes de calcular a compatibilidade.",
            code="resume_not_confirmed",
        )
    if not job_state.has_job or job_state.data is None:
        raise ValidationFailed(
            "Adicione e estruture uma vaga antes de calcular a compatibilidade.",
            code="missing_job",
        )
    if not job_state.confirmed:
        raise ValidationFailed(
            "Confirme os requisitos revisados da vaga antes de calcular a compatibilidade.",
            code="job_not_confirmed",
        )

    result = calculate_matching(
        resume_state.data,
        job_state.data,
        raw_resume_text=resume_state.raw_text,
    )
    session.store[SESSION_MATCHING_KEY] = result
    log.info(
        "matching_analyzed",
        extra={
            "overall_score": result.overall_score,
            "band": result.band,
            "matched_count": len(result.matched_keywords),
            "unverified_count": len(result.unverified_requirements),
        },
    )
    return result


@router.get(
    "/current",
    response_model=MatchingResult | None,
    summary="Retorna a última análise de compatibilidade calculada na sessão",
)
def get_current_matching(session: SessionData = Depends(get_session)) -> MatchingResult | None:
    existing = session.store.get(SESSION_MATCHING_KEY)
    if isinstance(existing, MatchingResult):
        return existing
    if isinstance(existing, dict):
        return MatchingResult.model_validate(existing)
    return None
