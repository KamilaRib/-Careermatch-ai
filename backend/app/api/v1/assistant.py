"""API v1 endpoints for Phase 6 — Contextual Career & Application Assistant."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.api.v1.ats_resume import SESSION_ATS_RESUME_KEY
from app.api.v1.jobs import get_session_job
from app.api.v1.matching import SESSION_MATCHING_KEY
from app.api.v1.resumes import _get_session_resume
from app.core.config import Settings
from app.core.logging import get_logger
from app.repositories.session_repository import SessionData
from app.schemas.assistant import (
    AssistantChatMessage,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantSessionState,
)
from app.schemas.ats_resume import ATSResumeResult
from app.schemas.matching import MatchingResult
from app.security.session import get_session
from app.services.assistant_service import (
    DEFAULT_SUGGESTED_PROMPTS,
    build_context_summary,
    generate_assistant_reply,
)

router = APIRouter(prefix="/assistant", tags=["assistant"])
log = get_logger("app.api.assistant")

SESSION_ASSISTANT_HISTORY_KEY = "assistant_chat_history"
MAX_HISTORY_MESSAGES = 30


def _get_session_contexts(
    session: SessionData,
) -> tuple[MatchingResult | None, ATSResumeResult | None]:
    raw_m = session.store.get(SESSION_MATCHING_KEY)
    matching: MatchingResult | None = None
    if isinstance(raw_m, MatchingResult):
        matching = raw_m
    elif isinstance(raw_m, dict):
        matching = MatchingResult.model_validate(raw_m)

    raw_a = session.store.get(SESSION_ATS_RESUME_KEY)
    ats_result: ATSResumeResult | None = None
    if isinstance(raw_a, ATSResumeResult):
        ats_result = raw_a
    elif isinstance(raw_a, dict):
        ats_result = ATSResumeResult.model_validate(raw_a)

    return matching, ats_result


def _get_session_history(session: SessionData) -> list[AssistantChatMessage]:
    raw = session.store.get(SESSION_ASSISTANT_HISTORY_KEY)
    if not isinstance(raw, list):
        return []
    out: list[AssistantChatMessage] = []
    for item in raw:
        if isinstance(item, AssistantChatMessage):
            out.append(item)
        elif isinstance(item, dict):
            out.append(AssistantChatMessage.model_validate(item))
    return out


@router.get(
    "/current",
    response_model=AssistantSessionState,
    summary="Retorna o histórico do assistente, resumo do contexto da sessão e perguntas sugeridas",
)
def get_assistant_state(session: SessionData = Depends(get_session)) -> AssistantSessionState:
    resume_state = _get_session_resume(session)
    job_state = get_session_job(session)
    matching, ats_result = _get_session_contexts(session)
    history = _get_session_history(session)
    ctx_summary = build_context_summary(resume_state, job_state, matching, ats_result)
    return AssistantSessionState(
        history=history,
        context_summary=ctx_summary,
        suggested_prompts=DEFAULT_SUGGESTED_PROMPTS,
    )


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    summary="Envia uma pergunta ao assistente contextual de candidatura",
)
async def chat_with_assistant(
    request: Request,
    payload: AssistantChatRequest,
    session: SessionData = Depends(get_session),
) -> AssistantChatResponse:
    resume_state = _get_session_resume(session)
    job_state = get_session_job(session)
    matching, ats_result = _get_session_contexts(session)
    settings: Settings = request.app.state.settings
    provider_override = getattr(request.app.state, "llm_provider", None)

    user_msg = AssistantChatMessage(
        id=uuid.uuid4().hex[:12],
        role="user",
        content=payload.message,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    reply_msg, ctx_summary = await generate_assistant_reply(
        message=payload.message,
        topic=payload.topic,
        resume_state=resume_state,
        job_state=job_state,
        matching=matching,
        ats_result=ats_result,
        settings=settings,
        use_deterministic_only=payload.use_deterministic_only,
        provider=provider_override,
    )

    history = _get_session_history(session)
    history.extend([user_msg, reply_msg])
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]
    session.store[SESSION_ASSISTANT_HISTORY_KEY] = history

    # Log only technical metadata — never log message text or personal data
    log.info(
        "assistant_chat_replied",
        extra={
            "topic": payload.topic,
            "method": reply_msg.response_method,
            "provider": reply_msg.provider_used,
            "history_count": len(history),
            "has_matching": ctx_summary.has_matching,
        },
    )

    return AssistantChatResponse(
        reply=reply_msg,
        history=history,
        context_summary=ctx_summary,
    )


@router.delete(
    "/history",
    response_model=AssistantSessionState,
    summary="Limpa o histórico de mensagens do assistente na sessão atual",
)
def clear_assistant_history(session: SessionData = Depends(get_session)) -> AssistantSessionState:
    session.store[SESSION_ASSISTANT_HISTORY_KEY] = []
    resume_state = _get_session_resume(session)
    job_state = get_session_job(session)
    matching, ats_result = _get_session_contexts(session)
    ctx_summary = build_context_summary(resume_state, job_state, matching, ats_result)
    log.info("assistant_history_cleared")
    return AssistantSessionState(
        history=[],
        context_summary=ctx_summary,
        suggested_prompts=DEFAULT_SUGGESTED_PROMPTS,
    )

