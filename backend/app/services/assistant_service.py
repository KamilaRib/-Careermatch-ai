"""Phase 6 — Contextual Career & Application Assistant Service.

Core guarantees:
1. Strictly read-only access to the ATS Matching score (`MatchingResult` is NEVER mutated by chat).
2. Zero fabrication: Never invents skills, roles, certifications, or personal data.
3. Explicit limitation notice when resume or job is missing or when evidence is insufficient.
4. Grounded references (`citations`) to the user's confirmed resume, job, and matching analysis.
5. Local Ollama integration with deterministic anti-fabrication guard and transparent fallback.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from app.ai.prompts.assistant_prompts import (
    ASSISTANT_SYSTEM_PROMPT,
    build_assistant_user_prompt,
)
from app.ai.providers.base import LLMProvider, get_llm_provider
from app.core.config import Settings
from app.core.errors import AIUnavailableError, ValidationFailed
from app.core.logging import get_logger
from app.schemas.assistant import (
    AssistantChatMessage,
    AssistantCitation,
    AssistantContextSummary,
    AssistantTopic,
)
from app.schemas.ats_resume import ATSResumeResult
from app.schemas.job import JobSessionState
from app.schemas.matching import MatchingResult
from app.schemas.resume import ResumeSessionState

log = get_logger("app.services.assistant")

DEFAULT_SUGGESTED_PROMPTS: list[str] = [
    "Qual é a minha compatibilidade atual com a vaga e quais são meus principais pontos fortes?",
    "Quais requisitos da vaga não foram identificados no meu currículo e como devo lidar com eles?",
    "Quais melhorias legítimas posso fazer no meu currículo sem inventar experiências?",
    "Como posso me preparar para a entrevista técnica desta vaga com base no meu perfil?",
    "Quais orientações de candidatura você recomenda para destacar minha experiência real?",
]


class _LLMAnswerSchema(BaseModel):
    answer: str = ""


def _norm(text: str) -> str:
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^\w\s/+.#%-]", " ", stripped.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def build_context_summary(
    resume_state: ResumeSessionState,
    job_state: JobSessionState,
    matching: MatchingResult | None,
    ats_result: ATSResumeResult | None,
) -> AssistantContextSummary:
    verified_skills: list[str] = []
    candidate_name = ""
    if resume_state.has_resume and resume_state.data:
        candidate_name = resume_state.data.personal_info.full_name or ""
        verified_skills = [
            s.name for s in resume_state.data.technical_skills if s.name and s.evidence_verified
        ]

    job_title = ""
    if job_state.has_job and job_state.data:
        job_title = job_state.data.title or ""

    unverified_reqs: list[str] = []
    overall_score: int | None = None
    band_label: str | None = None
    if matching is not None:
        overall_score = matching.overall_score
        band_label = matching.band_label
        unverified_reqs = list(matching.unverified_requirements)

    return AssistantContextSummary(
        has_resume=bool(resume_state.has_resume and resume_state.data is not None),
        resume_confirmed=bool(resume_state.confirmed),
        candidate_name=candidate_name,
        has_job=bool(job_state.has_job and job_state.data is not None),
        job_confirmed=bool(job_state.confirmed),
        job_title=job_title,
        has_matching=matching is not None,
        overall_score=overall_score,
        band_label=band_label,
        has_ats_resume=ats_result is not None,
        verified_skills=verified_skills,
        unverified_requirements=unverified_reqs,
    )


def _infer_topic(message: str, explicit_topic: AssistantTopic) -> AssistantTopic:
    if explicit_topic != "geral":
        return explicit_topic
    m_norm = _norm(message)
    if any(w in m_norm for w in ("entrevista", "pergunta", "recrutador", "argüicao", "arguicao")):
        return "entrevista"
    if any(w in m_norm for w in ("lacuna", "falta", "nao identificado", "ausente", "requisito")):
        return "lacunas"
    if any(w in m_norm for w in ("melhor", "curriculo", "resumo", "ats", "reescrever", "otimizar")):
        return "melhorias"
    if any(w in m_norm for w in ("candidatura", "aplicar", "linkedin", "carta", "abordagem", "estrategia")):
        return "candidatura"
    if any(w in m_norm for w in ("score", "nota", "compatibilidade", "pontuacao", "ponto forte")):
        return "compatibilidade"
    return "geral"


def _build_citations(
    resume_state: ResumeSessionState,
    job_state: JobSessionState,
    matching: MatchingResult | None,
    ats_result: ATSResumeResult | None,
) -> list[AssistantCitation]:
    citations: list[AssistantCitation] = []
    if resume_state.has_resume and resume_state.data:
        r = resume_state.data
        if r.professional_summary:
            citations.append(
                AssistantCitation(
                    source="curriculo",
                    label="Resumo Profissional Confirmado",
                    evidence=r.professional_summary[:260],
                )
            )
        if r.experiences:
            exp0 = r.experiences[0]
            citations.append(
                AssistantCitation(
                    source="curriculo",
                    label=f"Experiência: {exp0.role} ({exp0.company})",
                    evidence=exp0.evidence_quote or f"{exp0.role} | {exp0.company} | {exp0.period}",
                )
            )
    if job_state.has_job and job_state.data:
        j = job_state.data
        citations.append(
            AssistantCitation(
                source="vaga",
                label=f"Vaga Alvo: {j.title or 'Vaga analisada'}",
                evidence=f"Requisitos mapeados: {len(j.requirements)} | Senioridade: {j.seniority}",
            )
        )
    if matching is not None:
        citations.append(
            AssistantCitation(
                source="matching",
                label=f"Score Determinístico ATS: {matching.overall_score}% ({matching.band_label})",
                evidence=(
                    f"Comprovados: {', '.join(matching.matched_keywords[:5]) or 'nenhum'} | "
                    f"Não identificados: {', '.join(matching.unverified_requirements[:4]) or 'nenhum'}"
                ),
            )
        )
    if ats_result is not None:
        citations.append(
            AssistantCitation(
                source="ats",
                label="Currículo ATS Friendly Gerado",
                evidence=f"Palavras-chave destacadas: {', '.join(ats_result.incorporated_keywords[:6])}",
            )
        )
    return citations


def build_deterministic_assistant_reply(
    *,
    message: str,
    topic: AssistantTopic,
    resume_state: ResumeSessionState,
    job_state: JobSessionState,
    matching: MatchingResult | None,
    ats_result: ATSResumeResult | None,
) -> str:
    """Produces a comprehensive, 100% grounded Portuguese response based strictly on session data."""
    has_res = bool(resume_state.has_resume and resume_state.data is not None)
    has_job = bool(job_state.has_job and job_state.data is not None)

    if not has_res and not has_job:
        return (
            "Limitação de contexto: ainda não há currículo nem descrição de vaga carregados nesta sessão. "
            "Para receber orientações personalizadas baseadas em evidências reais, envie e confirme seu "
            "currículo em '/curriculo' e cadastre a vaga desejada em '/vaga'. Não invento qualificações "
            "nem avalio compatibilidade sem os documentos de origem."
        )

    if has_res and not has_job:
        r = resume_state.data
        assert r is not None
        skills = ", ".join(s.name for s in r.technical_skills[:8]) or "nenhuma listada"
        roles = ", ".join(f"{e.role} ({e.company})" for e in r.experiences[:3]) or "nenhuma experiência listada"
        return (
            f"Seu currículo está carregado na sessão (Competências comprovadas: {skills}; "
            f"Experiências: {roles}), porém ainda não há uma vaga analisada em '/vaga'. "
            "Limitação: sem os requisitos da vaga não é possível calcular o score de compatibilidade ATS "
            "nem apontar lacunas específicas. Cadastre e confirme a vaga em '/vaga' para destravar a "
            "análise comparativa completa."
        )

    if not has_res and has_job:
        j = job_state.data
        assert j is not None
        reqs = ", ".join(r.name for r in j.requirements[:6]) or "requisitos gerais"
        return (
            f"A vaga '{j.title or 'Vaga alvo'}' está registrada na sessão (principais requisitos: {reqs}), "
            "mas ainda não há um currículo carregado em '/curriculo'. "
            "Limitação: preciso do seu currículo confirmado para verificar quais requisitos você comprova "
            "com evidências reais. Envie seu currículo em '/curriculo' para prosseguir."
        )

    # Both resume and job exist
    r = resume_state.data
    j = job_state.data
    assert r is not None and j is not None

    inferred = _infer_topic(message, topic)
    skills_str = ", ".join(s.name for s in r.technical_skills if s.name) or "não especificadas"
    roles_str = (
        "; ".join(f"{e.role} na {e.company} ({e.period})" for e in r.experiences)
        or "sem experiências detalhadas"
    )
    score_str = (
        f"{matching.overall_score}% ({matching.band_label})"
        if matching is not None
        else "ainda não calculado (acesse '/compatibilidade' para calcular)"
    )
    matched_str = (
        ", ".join(matching.matched_keywords[:8])
        if matching and matching.matched_keywords
        else skills_str
    )
    unverified_str = (
        ", ".join(matching.unverified_requirements[:6])
        if matching and matching.unverified_requirements
        else "nenhum requisito pendente identificado"
    )

    if inferred == "compatibilidade":
        parts = [
            f"**Análise de Compatibilidade ({j.title or 'Vaga Alvo'}):**",
            f"- **Score Determinístico ATS:** {score_str}. Este índice é calculado de forma determinística e imutável pelo motor de matching, sem interferência do chat.",
            f"- **Competências e Requisitos Comprovados:** {matched_str}.",
            f"- **Histórico Profissional Verificado:** {roles_str}.",
            f"- **Requisitos Não Identificados no Currículo:** {unverified_str}.",
        ]
        if matching and matching.recommendations:
            parts.append(f"- **Observação Técnica:** {matching.recommendations[0]}")
        return "\n".join(parts)

    if inferred == "lacunas":
        parts = [
            f"**Competências Comprovadas vs. Requisitos Não Identificados ({j.title or 'Vaga Alvo'}):**",
            f"- **O que seu currículo já comprova literalmente:** {matched_str}.",
            f"- **O que consta na vaga mas NÃO foi identificado no seu currículo:** {unverified_str}.",
            "- **Política de Evidências:** A ausência de um termo no currículo significa apenas 'não comprovado no documento', e não que você não possua a competência. Além disso, tecnologias correlatas (como Docker ou AWS) não comprovam automaticamente competências distintas (como Kubernetes).",
            "- **Como agir com ética:** Se você já utilizou alguma das tecnologias não identificadas em projetos reais, adicione o fato verdadeiro na seção de experiências em '/curriculo'. Caso não tenha vivência prática nelas, mantenha-as fora do currículo e prepare-se para demonstrar na entrevista sua facilidade de aprendizado a partir da sua base sólida comprovada.",
        ]
        return "\n".join(parts)

    if inferred == "melhorias":
        parts = [
            f"**Melhorias Legítimas para o Currículo (Sem Inventar Qualificações):**",
            f"1. **Alinhamento do Resumo Profissional:** Destaque logo nas primeiras linhas suas competências já comprovadas que coincidem com a vaga ({matched_str}).",
            f"2. **Detalhamento das Experiências Reais ({roles_str}):** Explicite o contexto técnico das entregas que você realmente realizou utilizando {skills_str}.",
            f"3. **Cuidado com Termos Não Comprovados ({unverified_str}):** Não inclua esses termos sem evidência real. Utilize a rota '/curriculo-ats' para reordenar suas competências comprovadas em layout linear de coluna única compatível com parsers ATS.",
        ]
        return "\n".join(parts)

    if inferred == "entrevista":
        parts = [
            f"**Preparação para Entrevista ({j.title or 'Vaga Alvo'}):**",
            f"1. **Roteiro sobre Pontos Fortes Comprovados ({matched_str}):** Prepare exemplos práticos estruturados (Situação, Tarefa, Ação e Resultado real) baseados na sua atuação como {roles_str}.",
            f"2. **Como responder sobre requisitos não identificados ({unverified_str}):** Se o entrevistador perguntar sobre {unverified_str}, seja transparente sobre seu nível atual e conecte a resposta às tecnologias que você já domina comprovadamente ({skills_str}).",
            "3. **Perguntas sugeridas para fazer ao recrutador:** Questione sobre os principais desafios de arquitetura da equipe nos primeiros 90 dias e como as tecnologias da vaga são aplicadas no dia a dia.",
        ]
        return "\n".join(parts)

    # Default: 'candidatura' or 'geral'
    parts = [
        f"**Orientação Contextual de Candidatura ({j.title or 'Vaga Alvo'} — Score ATS: {score_str}):**",
        f"- **Posicionamento Profissional:** Apresente-se destacando sua trajetória comprovada ({roles_str}) e o domínio verificado em {matched_str}.",
        f"- **Transparência sobre Lacunas:** Os itens [{unverified_str}] não constam no currículo atual; só os mencione se houver experiência verídica.",
        "- **Próximo Passo Recomendado:** Gere e aprove a versão linear em '/curriculo-ats' para exportar o documento em PDF ou DOCX com texto 100% selecionável antes de submeter sua candidatura.",
    ]
    return "\n".join(parts)


def sanitize_assistant_answer(
    candidate_answer: str,
    baseline_answer: str,
    context_summary: AssistantContextSummary,
) -> str:
    """Blocks LLM responses that falsely claim unverified skills or fabricate a different ATS score."""
    cleaned = (candidate_answer or "").strip()
    if len(cleaned) < 25:
        return baseline_answer

    ans_norm = _norm(cleaned)

    # 1. Prevent score manipulation claims if matching exists
    if context_summary.overall_score is not None:
        real_score = context_summary.overall_score
        pct_matches = [int(m) for m in re.findall(r"\b(\d{1,3})\s*%", cleaned)]
        for pct in pct_matches:
            if pct != real_score and pct not in (100, 60, 80, 40, 30, 25, 20, 10, 5):
                # LLM cited a different compatibility percentage -> revert to grounded baseline
                return baseline_answer

    # 2. Prevent claiming that an unverified skill is already proven in the resume
    verified_norms = {_norm(s) for s in context_summary.verified_skills}
    for unv in context_summary.unverified_requirements:
        unv_norm = _norm(unv)
        if not unv_norm or len(unv_norm) < 3 or unv_norm in verified_norms:
            continue
        # Check if LLM claims the candidate "possui comprovadamente <unv>" or "domina <unv>"
        false_claim_patterns = [
            rf"comprovad\w+\s+em\s+{re.escape(unv_norm)}",
            rf"domina\s+{re.escape(unv_norm)}",
            rf"possui\s+experiencia\s+em\s+{re.escape(unv_norm)}",
        ]
        if any(re.search(pat, ans_norm) for pat in false_claim_patterns):
            return baseline_answer

    return cleaned


async def generate_assistant_reply(
    *,
    message: str,
    topic: AssistantTopic,
    resume_state: ResumeSessionState,
    job_state: JobSessionState,
    matching: MatchingResult | None,
    ats_result: ATSResumeResult | None,
    settings: Settings,
    use_deterministic_only: bool = False,
    provider: LLMProvider | None = None,
) -> tuple[AssistantChatMessage, AssistantContextSummary]:
    """Generates a contextual assistant reply without mutating any matching score or fabricating data."""
    context_summary = build_context_summary(resume_state, job_state, matching, ats_result)
    citations = _build_citations(resume_state, job_state, matching, ats_result)
    baseline_text = build_deterministic_assistant_reply(
        message=message,
        topic=topic,
        resume_state=resume_state,
        job_state=job_state,
        matching=matching,
        ats_result=ats_result,
    )

    method: str = "deterministic"
    provider_used: str = "deterministic"
    fallback_reason: str | None = None
    final_content = baseline_text

    # Only call LLM when both resume and job exist in the session and deterministic-only is not requested
    has_full_context = context_summary.has_resume and context_summary.has_job
    if has_full_context and not use_deterministic_only and settings.ai_configured:
        llm = provider or get_llm_provider(settings)
        context_lines = [
            f"Candidato: {context_summary.candidate_name or 'Anônimo'}",
            f"Currículo confirmado: {context_summary.resume_confirmed}",
            f"Competências comprovadas no currículo: {', '.join(context_summary.verified_skills) or 'nenhuma'}",
            f"Vaga alvo: {context_summary.job_title or 'Não informada'}",
            f"Score determinístico ATS: {context_summary.overall_score if context_summary.overall_score is not None else 'Não calculado'}%",
            f"Requisitos não identificados no currículo: {', '.join(context_summary.unverified_requirements) or 'nenhum'}",
        ]
        user_prompt = build_assistant_user_prompt(
            context_block="\n".join(context_lines),
            user_message=message,
            topic=topic,
            baseline_hint=baseline_text,
        )
        try:
            if hasattr(llm, "chat_assistant_fast"):
                llm_answer = await llm.chat_assistant_fast(  # type: ignore[attr-defined]
                    system_prompt=ASSISTANT_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                )
            else:
                structured = await llm.generate_structured(
                    system_prompt=ASSISTANT_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    schema=_LLMAnswerSchema,
                )
                llm_answer = structured.answer

            final_content = sanitize_assistant_answer(
                candidate_answer=llm_answer,
                baseline_answer=baseline_text,
                context_summary=context_summary,
            )
            model_label = getattr(llm, "model", settings.resolved_ai_model)
            method = "llm"
            provider_used = f"{llm.name}:{model_label}"
        except (AIUnavailableError, ValidationFailed) as exc:
            log.info("assistant_llm_fallback", extra={"reason": exc.message})
            if not settings.ai_fallback_deterministic:
                raise
            method = "deterministic_fallback"
            provider_used = "deterministic"
            fallback_reason = exc.message
            final_content = baseline_text

    reply_msg = AssistantChatMessage(
        id=uuid.uuid4().hex[:12],
        role="assistant",
        content=final_content,
        created_at=datetime.now(timezone.utc).isoformat(),
        citations=citations,
        response_method=method,  # type: ignore[arg-type]
        provider_used=provider_used,
        provider_fallback_reason=fallback_reason,
    )
    return reply_msg, context_summary
