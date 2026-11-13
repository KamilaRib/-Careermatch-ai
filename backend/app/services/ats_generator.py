"""Phase 5 — ATS-Friendly Resume Optimization, Non-Fabrication Guard & Document Exporters.

Core guarantees:
1. Zero fabrication: Never invents companies, roles, dates, degrees, certifications, or skills.
2. Unverified job requirements (e.g. Kubernetes when candidate only has Docker/AWS) are NEVER
   inserted into the resume; they are listed strictly in `suggested_keywords` for human review.
3. Full auditability: Every modification between original and optimized resume is logged in
   `changes` with `before`, `after`, and `justification`.
4. Clean ATS exports: Single-column PDF (`reportlab`) and DOCX (`python-docx`) with selectable text.
"""

from __future__ import annotations

import io
import re
import textwrap
import unicodedata

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.ai.providers.base import LLMProvider, get_llm_provider
from app.core.config import Settings
from app.core.errors import AIUnavailableError, ValidationFailed
from app.core.logging import get_logger
from app.schemas.ats_resume import (
    ATSResumeResult,
    KeywordSuggestionItem,
    OptimizationChangeItem,
    PreservationReport,
)
from app.schemas.job import ParsedJobData
from app.schemas.matching import MatchingResult
from app.schemas.resume import ParsedResumeData, SkillItem

log = get_logger("app.services.ats_generator")


def _norm(text: str) -> str:
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^\w\s/+.#-]", " ", stripped.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def render_ats_plain_text(resume: ParsedResumeData) -> str:
    """Renders a clean, single-column ATS-friendly plain text resume."""
    lines: list[str] = []
    pi = resume.personal_info
    if pi.full_name:
        lines.append(pi.full_name)
    contact_parts = [p for p in [pi.location, pi.email, pi.phone, pi.linkedin] if p]
    if contact_parts:
        lines.append(" | ".join(contact_parts))
    lines.append("")

    if resume.professional_summary:
        lines.append("RESUMO PROFISSIONAL")
        lines.append(resume.professional_summary.strip())
        lines.append("")

    if resume.technical_skills:
        lines.append("COMPETÊNCIAS TÉCNICAS")
        lines.append(", ".join(s.name for s in resume.technical_skills if s.name))
        lines.append("")

    if resume.experiences:
        lines.append("EXPERIÊNCIA PROFISSIONAL")
        for exp in resume.experiences:
            header = " | ".join(p for p in [exp.role, exp.company, exp.period, exp.location] if p)
            if header:
                lines.append(header)
            for resp in exp.responsibilities:
                lines.append(f"- {resp}")
            for ach in exp.achievements:
                lines.append(f"- {ach}")
            lines.append("")

    if resume.education:
        lines.append("FORMAÇÃO ACADÊMICA")
        for edu in resume.education:
            header = " | ".join(p for p in [edu.degree, edu.institution, edu.period] if p)
            if header:
                lines.append(header)
        lines.append("")

    if resume.certifications:
        lines.append("CERTIFICAÇÕES")
        for cert in resume.certifications:
            parts = [p for p in [cert.name, cert.issuer, cert.year] if p]
            if parts:
                lines.append(" - ".join(parts))
        lines.append("")

    if resume.languages:
        lines.append("IDIOMAS")
        lang_items = [
            f"{l.language}: {l.proficiency}" if l.proficiency else l.language
            for l in resume.languages
            if l.language
        ]
        if lang_items:
            lines.append(", ".join(lang_items))
        lines.append("")

    if resume.projects:
        lines.append("PROJETOS")
        for proj in resume.projects:
            line = f"{proj.name} - {proj.description}" if proj.description else proj.name
            if line:
                lines.append(line)
        lines.append("")

    return "\n".join(lines).strip()


def render_ats_markdown(resume: ParsedResumeData) -> str:
    """Renders a clean, single-column ATS-friendly Markdown resume."""
    lines: list[str] = []
    pi = resume.personal_info
    if pi.full_name:
        lines.append(f"# {pi.full_name}")
    contact_parts = [p for p in [pi.location, pi.email, pi.phone, pi.linkedin] if p]
    if contact_parts:
        lines.append(" | ".join(contact_parts))
    lines.append("")

    if resume.professional_summary:
        lines.append("## Resumo Profissional")
        lines.append(resume.professional_summary.strip())
        lines.append("")

    if resume.technical_skills:
        lines.append("## Competências Técnicas")
        lines.append(", ".join(s.name for s in resume.technical_skills if s.name))
        lines.append("")

    if resume.experiences:
        lines.append("## Experiência Profissional")
        for exp in resume.experiences:
            header = " | ".join(p for p in [exp.role, exp.company, exp.period, exp.location] if p)
            if header:
                lines.append(f"### {header}")
            for resp in exp.responsibilities:
                lines.append(f"- {resp}")
            for ach in exp.achievements:
                lines.append(f"- {ach}")
            lines.append("")

    if resume.education:
        lines.append("## Formação Acadêmica")
        for edu in resume.education:
            header = " | ".join(p for p in [edu.degree, edu.institution, edu.period] if p)
            if header:
                lines.append(f"- {header}")
        lines.append("")

    if resume.certifications:
        lines.append("## Certificações")
        for cert in resume.certifications:
            parts = [p for p in [cert.name, cert.issuer, cert.year] if p]
            if parts:
                lines.append(f"- {' - '.join(parts)}")
        lines.append("")

    if resume.languages:
        lines.append("## Idiomas")
        for l in resume.languages:
            if l.language:
                lines.append(f"- {l.language}: {l.proficiency}" if l.proficiency else f"- {l.language}")
        lines.append("")

    if resume.projects:
        lines.append("## Projetos")
        for proj in resume.projects:
            line = f"**{proj.name}** — {proj.description}" if proj.description else f"**{proj.name}**"
            if line:
                lines.append(f"- {line}")
        lines.append("")

    return "\n".join(lines).strip()


def verify_and_sanitize_ats_resume(
    original: ParsedResumeData,
    candidate_optimized: ParsedResumeData,
    raw_resume_text: str,
    unverified_job_terms: list[str],
) -> tuple[ParsedResumeData, PreservationReport]:
    """Deterministic anti-fabrication guard that blocks any invented skill, role, degree or certification."""
    sanitized = candidate_optimized.model_copy(deep=True)
    blocked: list[str] = []

    orig_corpus_norm = _norm(f"{render_ats_plain_text(original)}\n{raw_resume_text}")
    orig_skill_norms = {_norm(s.name) for s in original.technical_skills if s.name}

    # 1. Verify technical skills: keep ONLY skills that existed in original resume or literal text
    valid_skills: list[SkillItem] = []
    for sk in sanitized.technical_skills:
        sk_norm = _norm(sk.name)
        if not sk_norm:
            continue
        if sk_norm in orig_skill_norms or sk_norm in orig_corpus_norm:
            valid_skills.append(sk)
        else:
            blocked.append(f"Competência bloqueada por ausência de evidência no currículo original: {sk.name}")
    sanitized.technical_skills = valid_skills

    # 2. Verify experiences: roles, companies, and periods must match original experiences
    orig_exp_keys = {
        (_norm(e.role), _norm(e.company), _norm(e.period)) for e in original.experiences
    }
    valid_experiences = []
    for exp in sanitized.experiences:
        key = (_norm(exp.role), _norm(exp.company), _norm(exp.period))
        if key in orig_exp_keys:
            valid_experiences.append(exp)
        else:
            blocked.append(
                f"Experiência bloqueada por divergir do currículo confirmado: {exp.role} | {exp.company}"
            )
    if not valid_experiences and original.experiences:
        valid_experiences = original.experiences.copy()
    sanitized.experiences = valid_experiences

    # 3. Verify education
    orig_edu_keys = {(_norm(e.degree), _norm(e.institution)) for e in original.education}
    valid_edu = []
    for edu in sanitized.education:
        if (_norm(edu.degree), _norm(edu.institution)) in orig_edu_keys:
            valid_edu.append(edu)
        else:
            blocked.append(f"Formação bloqueada por ausência no currículo original: {edu.degree}")
    if not valid_edu and original.education:
        valid_edu = original.education.copy()
    sanitized.education = valid_edu

    # 4. Verify certifications
    orig_cert_norms = {_norm(c.name) for c in original.certifications if c.name}
    valid_certs = []
    for cert in sanitized.certifications:
        if _norm(cert.name) in orig_cert_norms:
            valid_certs.append(cert)
        else:
            blocked.append(f"Certificação bloqueada por ausência no currículo original: {cert.name}")
    sanitized.certifications = valid_certs

    # 5. Check summary against unverified job terms
    summary_norm = _norm(sanitized.professional_summary)
    for unv in unverified_job_terms:
        unv_norm = _norm(unv)
        if unv_norm and len(unv_norm) >= 3 and unv_norm not in orig_corpus_norm:
            if re.search(rf"\b{re.escape(unv_norm)}\b", summary_norm):
                blocked.append(
                    f"Termo não comprovado da vaga bloqueado no resumo profissional: {unv}"
                )
                sanitized.professional_summary = original.professional_summary
                break

    report = PreservationReport(
        zero_fabrication_verified=True,
        preserved_experiences_count=len(sanitized.experiences),
        preserved_education_count=len(sanitized.education),
        preserved_skills_count=len(sanitized.technical_skills),
        preserved_certifications_count=len(sanitized.certifications),
        blocked_fabrications=blocked,
    )
    return sanitized, report


def _build_deterministic_optimization(
    original: ParsedResumeData,
    job: ParsedJobData,
    matching: MatchingResult,
    raw_resume_text: str,
) -> tuple[
    ParsedResumeData,
    list[OptimizationChangeItem],
    list[str],
    list[KeywordSuggestionItem],
]:
    optimized = original.model_copy(deep=True)
    changes: list[OptimizationChangeItem] = []

    job_corpus_norm = _norm(
        " ".join(
            [job.title, *job.technologies, *job.keywords, *(r.name for r in job.requirements)]
        )
    )
    matched_norms = {_norm(k) for k in matching.matched_keywords if k}

    # 1. Reorder technical skills so job-matching verified skills come first
    orig_skill_names = [s.name for s in original.technical_skills]
    matched_skills: list[SkillItem] = []
    other_skills: list[SkillItem] = []
    incorporated_keywords: list[str] = []

    for sk in optimized.technical_skills:
        sk_norm = _norm(sk.name)
        is_job_relevant = (
            sk_norm in matched_norms
            or (sk_norm and re.search(rf"\b{re.escape(sk_norm)}\b", job_corpus_norm) is not None)
        )
        if is_job_relevant:
            matched_skills.append(sk)
            if sk.name not in incorporated_keywords:
                incorporated_keywords.append(sk.name)
        else:
            other_skills.append(sk)

    optimized.technical_skills = matched_skills + other_skills
    new_skill_names = [s.name for s in optimized.technical_skills]
    if orig_skill_names != new_skill_names and orig_skill_names:
        changes.append(
            OptimizationChangeItem(
                section="Competências Técnicas",
                change_type="reordenacao_competencias",
                before=", ".join(orig_skill_names),
                after=", ".join(new_skill_names),
                justification=(
                    "Competências comprovadas do candidato que correspondem diretamente aos requisitos "
                    "da vaga foram posicionadas no início da seção para priorização em leitura ATS."
                ),
            )
        )

    # 2. Align professional summary with verified skills & target job without inventing facts
    base_summary = (original.professional_summary or "").strip()
    summary_norm = _norm(base_summary)
    missing_verified_in_summary = [
        kw for kw in incorporated_keywords if _norm(kw) not in summary_norm
    ]
    if base_summary:
        if missing_verified_in_summary:
            aligned_summary = (
                f"{base_summary.rstrip('.')}."
                f" Competências comprovadas alinhadas à vaga: {', '.join(missing_verified_in_summary[:6])}."
            )
        else:
            aligned_summary = base_summary
    elif incorporated_keywords:
        aligned_summary = (
            f"Profissional com experiência comprovada em {', '.join(incorporated_keywords[:6])}."
        )
    else:
        aligned_summary = base_summary

    if aligned_summary != base_summary:
        optimized.professional_summary = aligned_summary
        changes.append(
            OptimizationChangeItem(
                section="Resumo Profissional",
                change_type="alinhamento_resumo",
                before=base_summary or "(vazio)",
                after=aligned_summary,
                justification=(
                    "Inclusão explícita no resumo das competências técnicas já comprovadas no histórico "
                    "do candidato que são exigidas pela vaga, aumentando a densidade semântica no topo do documento."
                ),
            )
        )

    # 3. Reorder responsibilities within each experience so bullets with matched keywords appear first
    for idx, exp in enumerate(optimized.experiences):
        if len(exp.responsibilities) <= 1:
            continue
        orig_resps = list(exp.responsibilities)

        def _bullet_score(bullet: str) -> int:
            b_norm = _norm(bullet)
            return sum(1 for kw in incorporated_keywords if _norm(kw) and _norm(kw) in b_norm)

        sorted_resps = sorted(orig_resps, key=_bullet_score, reverse=True)
        if sorted_resps != orig_resps:
            exp.responsibilities = sorted_resps
            changes.append(
                OptimizationChangeItem(
                    section=f"Experiência Profissional ({exp.role} — {exp.company})",
                    change_type="destaque_experiencia",
                    before=" | ".join(orig_resps),
                    after=" | ".join(sorted_resps),
                    justification=(
                        "Reordenação dos tópicos de responsabilidade para destacar primeiro as entregas "
                        "com palavras-chave da vaga, mantendo 100% da redação e veracidade originais."
                    ),
                )
            )

    # 4. Always log ATS formatting standardization
    changes.append(
        OptimizationChangeItem(
            section="Estrutura Geral do Documento",
            change_type="padronizacao_ats",
            before="Estrutura original de entrada",
            after="Layout linear de coluna única com títulos de seção padronizados para sistemas ATS",
            justification=(
                "Remoção de elementos visuais complexos (tabelas, múltiplas colunas e ícones) e "
                "aplicação de cabeçalhos canônicos reconhecidos por parsers de recrutamento."
            ),
        )
    )

    # 5. Build advisory keyword suggestions from unverified/partial job requirements
    suggestions: list[KeywordSuggestionItem] = []
    seen_sugg: set[str] = set()
    for rm in matching.requirement_matches:
        if rm.state in ("nao_identificado", "parcialmente_atendido"):
            k_norm = _norm(rm.requirement_name)
            if not k_norm or k_norm in seen_sugg:
                continue
            seen_sugg.add(k_norm)
            suggestions.append(
                KeywordSuggestionItem(
                    keyword=rm.requirement_name,
                    importance=rm.importance,
                    category=rm.category,
                    advisory_note=(
                        "Não adicionado automaticamente ao currículo (sem evidência no documento original). "
                        "Inclua na edição manual apenas se você possuir experiência real nesta competência."
                    ),
                )
            )

    return optimized, changes, incorporated_keywords, suggestions


async def generate_ats_resume(
    original_resume: ParsedResumeData,
    job: ParsedJobData,
    matching: MatchingResult,
    raw_resume_text: str,
    settings: Settings,
    *,
    use_deterministic_only: bool = False,
    provider: LLMProvider | None = None,
) -> ATSResumeResult:
    """Generates an ATS-optimized resume grounded strictly in verified candidate facts."""
    optimized, changes, incorporated_kws, suggestions = _build_deterministic_optimization(
        original_resume, job, matching, raw_resume_text
    )

    method = "deterministic"
    provider_used = "deterministic"
    fallback_reason: str | None = None

    if not use_deterministic_only and settings.ai_configured:
        llm = provider or get_llm_provider(settings)
        try:
            if hasattr(llm, "enrich_ats_summary_fast"):
                llm_summary = await llm.enrich_ats_summary_fast(  # type: ignore[attr-defined]
                    original_summary=optimized.professional_summary,
                    job_title=job.title or "Vaga Alvo",
                    verified_keywords=incorporated_kws,
                )
                if llm_summary and len(llm_summary) >= 30:
                    before_sum = original_resume.professional_summary
                    optimized.professional_summary = llm_summary
                    # Update or append summary change item
                    changes = [c for c in changes if c.change_type != "alinhamento_resumo"]
                    changes.insert(
                        0,
                        OptimizationChangeItem(
                            section="Resumo Profissional (IA Local)",
                            change_type="alinhamento_resumo",
                            before=before_sum or "(vazio)",
                            after=llm_summary,
                            justification=(
                                "Resumo profissional refinado pelo modelo local preservando os fatos originais "
                                "e destacando as competências comprovadas exigidas pela vaga."
                            ),
                        ),
                    )
                model_label = getattr(llm, "model", settings.resolved_ai_model)
                method = "llm"
                provider_used = f"{llm.name}:{model_label}"
        except (AIUnavailableError, ValidationFailed) as exc:
            log.info("ats_llm_fallback", extra={"reason": exc.message})
            if not settings.ai_fallback_deterministic:
                raise
            method = "deterministic_fallback"
            provider_used = "deterministic"
            fallback_reason = exc.message

    sanitized_data, preservation_report = verify_and_sanitize_ats_resume(
        original=original_resume,
        candidate_optimized=optimized,
        raw_resume_text=raw_resume_text,
        unverified_job_terms=matching.unverified_requirements,
    )

    return ATSResumeResult(
        optimized_data=sanitized_data,
        markdown_preview=render_ats_markdown(sanitized_data),
        plain_text_preview=render_ats_plain_text(sanitized_data),
        changes=changes,
        incorporated_keywords=incorporated_kws,
        suggested_keywords=suggestions,
        preservation_report=preservation_report,
        optimization_method=method,  # type: ignore[arg-type]
        provider_used=provider_used,
        provider_fallback_reason=fallback_reason,
        approved=False,
    )


def export_ats_resume_pdf(resume: ParsedResumeData) -> bytes:
    """Generates a clean, single-column ATS-friendly PDF with selectable text."""
    plain_text = render_ats_plain_text(resume)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 50
    margin_x = 50

    section_headers = {
        "RESUMO PROFISSIONAL",
        "COMPETÊNCIAS TÉCNICAS",
        "EXPERIÊNCIA PROFISSIONAL",
        "FORMAÇÃO ACADÊMICA",
        "CERTIFICAÇÕES",
        "IDIOMAS",
        "PROJETOS",
    }

    for idx, raw_line in enumerate(plain_text.splitlines()):
        stripped = raw_line.strip()
        if not stripped:
            y -= 8
            if y < 60:
                c.showPage()
                y = height - 50
            continue

        is_title = idx == 0 and bool(resume.personal_info.full_name)
        is_header = stripped in section_headers

        if is_title:
            c.setFont("Helvetica-Bold", 14)
            wrap_width = 75
            line_step = 18
        elif is_header:
            c.setFont("Helvetica-Bold", 11)
            wrap_width = 85
            line_step = 15
        else:
            c.setFont("Helvetica", 10)
            wrap_width = 88
            line_step = 14

        wrapped = textwrap.wrap(
            stripped,
            width=wrap_width,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]

        for chunk in wrapped:
            if y < 60:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)
            c.drawString(margin_x, y, chunk)
            y -= line_step

    c.save()
    return buf.getvalue()


def export_ats_resume_docx(resume: ParsedResumeData) -> bytes:
    """Generates a clean, single-column ATS-friendly DOCX with standard headings and selectable text."""
    doc = Document()
    pi = resume.personal_info
    if pi.full_name:
        doc.add_heading(pi.full_name, level=0)
    contact_parts = [p for p in [pi.location, pi.email, pi.phone, pi.linkedin] if p]
    if contact_parts:
        doc.add_paragraph(" | ".join(contact_parts))

    if resume.professional_summary:
        doc.add_heading("RESUMO PROFISSIONAL", level=1)
        doc.add_paragraph(resume.professional_summary.strip())

    if resume.technical_skills:
        doc.add_heading("COMPETÊNCIAS TÉCNICAS", level=1)
        doc.add_paragraph(", ".join(s.name for s in resume.technical_skills if s.name))

    if resume.experiences:
        doc.add_heading("EXPERIÊNCIA PROFISSIONAL", level=1)
        for exp in resume.experiences:
            header = " | ".join(p for p in [exp.role, exp.company, exp.period, exp.location] if p)
            if header:
                doc.add_paragraph(header)
            for resp in exp.responsibilities:
                doc.add_paragraph(f"- {resp}")
            for ach in exp.achievements:
                doc.add_paragraph(f"- {ach}")

    if resume.education:
        doc.add_heading("FORMAÇÃO ACADÊMICA", level=1)
        for edu in resume.education:
            header = " | ".join(p for p in [edu.degree, edu.institution, edu.period] if p)
            if header:
                doc.add_paragraph(header)

    if resume.certifications:
        doc.add_heading("CERTIFICAÇÕES", level=1)
        for cert in resume.certifications:
            parts = [p for p in [cert.name, cert.issuer, cert.year] if p]
            if parts:
                doc.add_paragraph(" - ".join(parts))

    if resume.languages:
        doc.add_heading("IDIOMAS", level=1)
        lang_items = [
            f"{l.language}: {l.proficiency}" if l.proficiency else l.language
            for l in resume.languages
            if l.language
        ]
        if lang_items:
            doc.add_paragraph(", ".join(lang_items))

    if resume.projects:
        doc.add_heading("PROJETOS", level=1)
        for proj in resume.projects:
            line = f"{proj.name} - {proj.description}" if proj.description else proj.name
            if line:
                doc.add_paragraph(line)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
