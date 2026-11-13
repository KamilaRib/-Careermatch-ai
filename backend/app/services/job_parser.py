"""Job description parsing service (LLM + deterministic fallback + evidence validation)."""

from __future__ import annotations

import re

from app.ai.prompts.job_prompts import JOB_PARSE_SYSTEM_PROMPT, build_job_parse_user_prompt
from app.ai.providers.base import LLMProvider, get_llm_provider
from app.ai.validators.evidence_validator import is_evidence_grounded
from app.core.config import Settings
from app.core.errors import AIUnavailableError, ValidationFailed
from app.core.logging import get_logger
from app.schemas.job import (
    JobRequirementItem,
    ParsedJobData,
    RequirementCategory,
    RequirementImportance,
)
from app.schemas.resume import EvidenceValidationReport, ExtractionMethod

log = get_logger("app.services.job_parser")

MIN_JOB_CHARS = 30

# Canonical known technical tokens for deterministic extraction when no LLM is running
KNOWN_TECH_PATTERNS: dict[str, tuple[str, ...]] = {
    "Python": (r"\bpython\b",),
    "FastAPI": (r"\bfastapi\b",),
    "Django": (r"\bdjango\b",),
    "Flask": (r"\bflask\b",),
    "TypeScript": (r"\btypescript\b",),
    "JavaScript": (r"\bjavascript\b",),
    "React": (r"\breact(?:\.js|js)?\b",),
    "Node.js": (r"\bnode(?:\.js|js)?\b",),
    "PostgreSQL": (r"\bpostgres(?:ql)?\b",),
    "MySQL": (r"\bmysql\b",),
    "MongoDB": (r"\bmongodb\b",),
    "Redis": (r"\bredis\b",),
    "Docker": (r"\bdocker\b",),
    "Kubernetes": (r"\bkubernetes\b", r"\bk8s\b"),
    "AWS": (r"\baws\b", r"\bamazon web services\b"),
    "GCP": (r"\bgcp\b", r"\bgoogle cloud\b"),
    "Azure": (r"\bazure\b",),
    "Git": (r"\bgit\b",),
    "CI/CD": (r"\bci/cd\b", r"\bintegração contínua\b"),
    "Pytest": (r"\bpytest\b",),
    "REST API": (r"\bapis?\s+rest(?:ful)?\b", r"\brest(?:ful)?\s+apis?\b"),
    "GraphQL": (r"\bgraphql\b",),
    "Tailwind CSS": (r"\btailwind(?:\s*css)?\b",),
    "SQL": (r"\bsql\b",),
    "Kafka": (r"\bkafka\b",),
    "Terraform": (r"\bterraform\b",),
}

SOFT_SKILL_PATTERNS: dict[str, str] = {
    "Comunicação": r"\bcomunica[çc][ãa]o\b",
    "Trabalho em equipe": r"\btrabalho em equipe\b|\bcolabora[çc][ãa]o\b",
    "Liderança": r"\blideran[çc]a\b|\bmentoria\b",
    "Resolução de problemas": r"\bresolu[çc][ãa]o de problemas\b",
    "Proatividade": r"\bproatividade\b|\bautonomia\b",
}

_YEARS_RE = re.compile(r"(\d{1,2})\+?\s*(?:anos?|years?)\s+de\s+experi[êe]ncia", re.IGNORECASE)


def validate_job_evidence(raw_text: str, data: ParsedJobData) -> EvidenceValidationReport:
    """Verifies that every extracted job requirement is grounded in `raw_text`."""
    total = 0
    verified = 0
    warnings: list[str] = []

    for req in data.requirements:
        total += 1
        ok = is_evidence_grounded(raw_text, req.evidence_quote, req.name)
        req.evidence_verified = ok
        if ok:
            verified += 1
        else:
            warnings.append(
                f"Requisito '{req.name}' não possui comprovação literal no texto da vaga."
            )

    return EvidenceValidationReport(
        total_items_checked=total,
        verified_items=verified,
        unverified_warnings=warnings,
    )


def _detect_importance(line: str, section_mode: RequirementImportance) -> tuple[RequirementImportance, bool]:
    low = line.lower()
    is_elim = any(w in low for w in ("eliminatório", "eliminatorio", "imprescindível", "imprescindivel"))
    if any(w in low for w in ("desejável", "desejavel", "diferencial", "nice to have", "plus", "será um diferencial")):
        return "desejavel", False
    if any(w in low for w in ("obrigatório", "obrigatorio", "necessário", "necessario", "exigido", "must have")) or is_elim:
        return "obrigatorio", is_elim
    return section_mode, is_elim


def _categorize_line(line: str) -> RequirementCategory:
    low = line.lower()
    if any(w in low for w in ("graduação", "graduacao", "bacharelado", "formação", "formacao", "certificação", "certificacao", "superior")):
        return "formacao_certificacoes"
    if any(w in low for w in ("inglês", "ingles", "espanhol", "idioma")):
        return "idiomas"
    if _YEARS_RE.search(line) or "experiência com" in low or "experiencia com" in low or "vivência" in low:
        return "experiencia_profissional"
    if any(re.search(pat, low) for pat in SOFT_SKILL_PATTERNS.values()):
        return "competencias_comportamentais"
    return "competencias_tecnicas"


def parse_job_deterministic(raw_text: str) -> ParsedJobData:
    """Rule-based deterministic job parser when LLM is unavailable."""
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        return ParsedJobData()

    # Title and Company from first lines (skipping generic 1-word headers like 'Vaga')
    header_line = lines[0]
    for candidate_ln in lines[:3]:
        stripped_hdr = re.sub(
            r"^(?:vaga|oportunidade|cargo)\s*[:\-–—]?\s*", "", candidate_ln, flags=re.IGNORECASE
        ).strip()
        if len(stripped_hdr) >= 5:
            header_line = stripped_hdr
            break

    parts = [p.strip() for p in re.split(r"[|—–]| - ", header_line) if p.strip()]
    title = parts[0][:180] if parts else header_line[:180]
    company = parts[1][:180] if len(parts) > 1 else ""

    for ln in lines[:6]:
        m_comp = re.search(r"^(?:empresa|company)\s*:\s*(.+)$", ln, re.IGNORECASE)
        if m_comp:
            company = m_comp.group(1).strip()[:180]
        m_cargo = re.search(r"^(?:cargo|vaga|posição|posicao)\s*:\s*(.+)$", ln, re.IGNORECASE)
        if m_cargo:
            title = m_cargo.group(1).strip()[:180]

    low_all = raw_text.lower()
    # Seniority
    seniority = "Não especificado"
    for label, pat in (
        ("Sênior", r"\bs[êe]nior\b|\bsr\.?\b"),
        ("Pleno", r"\bpleno\b|\bmid(?:-level)?\b|\bpl\.?\b"),
        ("Júnior", r"\bj[úu]nior\b|\bjr\.?\b"),
        ("Especialista / Staff", r"\bespecialista\b|\bstaff\b|\bprincipal\b|\btech lead\b"),
        ("Estágio", r"\best[áa]gio\b|\bintern\b"),
    ):
        if re.search(pat, low_all):
            seniority = label
            break

    # Work model
    work_model = "Não especificado"
    for label, pat in (
        ("Remoto", r"\b100%\s*remoto\b|\bremoto\b|\bhome\s*office\b|\bremote\b"),
        ("Híbrido", r"\bh[íi]brido\b|\bhybrid\b"),
        ("Presencial", r"\bpresencial\b|\bon-?site\b"),
    ):
        if re.search(pat, low_all):
            work_model = label
            break

    # Location
    location = ""
    for ln in lines[:10]:
        loc_m = re.search(
            r"([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+)*\s*[-/,]\s*[A-Z]{2})\b", ln
        )
        if loc_m:
            location = loc_m.group(1).strip()
            break

    years_m = _YEARS_RE.search(raw_text)
    exp_years_str = years_m.group(0) if years_m else ""

    responsibilities: list[str] = []
    requirements: list[JobRequirementItem] = []
    seen_reqs: set[str] = set()

    mode: Literal["intro", "resp", "req"] = "intro"
    section_importance: RequirementImportance = "obrigatorio"

    for ln in lines[1:]:
        clean_hdr = re.sub(r"^[\d.#*\-–—•\s]+|[:\s#*]+$", "", ln).lower()
        if clean_hdr in {
            "responsabilidades",
            "atribuições",
            "atribuicoes",
            "o que você vai fazer",
            "atividades",
            "desafios",
        }:
            mode = "resp"
            continue
        if clean_hdr in {
            "requisitos",
            "requisitos obrigatórios",
            "requisitos obrigatorios",
            "qualificações",
            "qualificacoes",
            "o que buscamos",
            "o que esperamos",
        }:
            mode = "req"
            section_importance = "obrigatorio"
            continue
        if clean_hdr in {
            "diferenciais",
            "requisitos desejáveis",
            "requisitos desejaveis",
            "desejável",
            "desejavel",
            "nice to have",
        }:
            mode = "req"
            section_importance = "desejavel"
            continue

        item_text = ln.lstrip("-•*–— ").strip()
        if not item_text:
            continue

        if mode == "resp" and (ln.startswith(("-", "•", "*", "–")) or len(item_text) > 15):
            responsibilities.append(item_text[:300])
            continue

        if mode == "req" or ln.startswith(("-", "•", "*", "–")):
            imp, is_elim = _detect_importance(item_text, section_importance if mode == "req" else "contextual")
            cat = _categorize_line(item_text)
            yr_m = _YEARS_RE.search(item_text)
            min_yrs = int(yr_m.group(1)) if yr_m else None
            key = item_text.lower()[:120]
            if key not in seen_reqs:
                seen_reqs.add(key)
                requirements.append(
                    JobRequirementItem(
                        name=item_text[:220],
                        category=cat,
                        importance=imp,
                        is_eliminatory=is_elim,
                        min_years=min_yrs,
                        evidence_quote=ln[:800],
                        evidence_verified=True,
                    )
                )

    # Extract explicit technical skills with line-level evidence
    technologies: list[str] = []
    for tech_name, patterns in KNOWN_TECH_PATTERNS.items():
        for ln in lines:
            if any(re.search(p, ln.lower()) for p in patterns):
                technologies.append(tech_name)
                tech_key = tech_name.lower()
                if tech_key not in seen_reqs:
                    seen_reqs.add(tech_key)
                    imp, is_elim = _detect_importance(ln, "obrigatorio")
                    requirements.append(
                        JobRequirementItem(
                            name=tech_name,
                            category="competencias_tecnicas",
                            importance=imp,
                            is_eliminatory=is_elim,
                            evidence_quote=ln[:800],
                            evidence_verified=True,
                        )
                    )
                break

    # Extract soft skills mentioned
    for soft_name, pat in SOFT_SKILL_PATTERNS.items():
        for ln in lines:
            if re.search(pat, ln.lower()):
                soft_key = soft_name.lower()
                if soft_key not in seen_reqs:
                    seen_reqs.add(soft_key)
                    requirements.append(
                        JobRequirementItem(
                            name=soft_name,
                            category="competencias_comportamentais",
                            importance="contextual",
                            evidence_quote=ln[:800],
                            evidence_verified=True,
                        )
                    )
                break

    # Languages
    languages: list[str] = []
    for lang_label, pat in (
        ("Inglês", r"\bingl[êe]s\b|\benglish\b"),
        ("Espanhol", r"\bespanhol\b|\bspanish\b"),
        ("Português", r"\bportugu[êe]s\b"),
    ):
        for ln in lines:
            if re.search(pat, ln.lower()):
                languages.append(lang_label)
                break

    # Education
    education_required = ""
    for ln in lines:
        if any(w in ln.lower() for w in ("bacharelado", "graduação", "graduacao", "ensino superior", "ciência da computação")):
            education_required = ln.lstrip("-•*–— ").strip()[:240]
            break

    keywords = list(dict.fromkeys([*technologies, *languages]))

    return ParsedJobData(
        title=title,
        company=company,
        location=location,
        work_model=work_model,
        seniority=seniority,
        experience_years_required=exp_years_str,
        education_required=education_required,
        responsibilities=responsibilities,
        requirements=requirements,
        technologies=technologies,
        languages=languages,
        keywords=keywords,
    )


async def parse_job_text(
    raw_text: str,
    settings: Settings,
    *,
    provider: LLMProvider | None = None,
    use_deterministic_only: bool = False,
) -> tuple[ParsedJobData, ExtractionMethod, str, str | None, EvidenceValidationReport]:
    """Parses job description via LLMProvider or deterministic fallback and validates evidence."""
    cleaned = (raw_text or "").strip()
    if len(re.sub(r"\s+", "", cleaned)) < MIN_JOB_CHARS:
        raise ValidationFailed(
            "A descrição da vaga é muito curta para análise (mínimo de 30 caracteres úteis).",
            code="job_text_too_short",
        )

    fallback_reason: str | None = None
    if use_deterministic_only:
        data = parse_job_deterministic(cleaned)
        method: ExtractionMethod = "deterministic_fallback"
        provider_used = "deterministic"
    else:
        try:
            llm = provider or get_llm_provider(settings)
            if getattr(llm, "name", "") == "ollama":
                baseline = parse_job_deterministic(cleaned)
                if hasattr(llm, "enrich_job_fast"):
                    data = await llm.enrich_job_fast(cleaned, baseline)  # type: ignore[attr-defined]
                else:
                    data = await llm.generate_structured(
                        system_prompt=JOB_PARSE_SYSTEM_PROMPT,
                        user_prompt=build_job_parse_user_prompt(cleaned),
                        schema=ParsedJobData,
                    )
            else:
                data = await llm.generate_structured(
                    system_prompt=JOB_PARSE_SYSTEM_PROMPT,
                    user_prompt=build_job_parse_user_prompt(cleaned),
                    schema=ParsedJobData,
                )
            method = "llm"
            provider_used = f"{llm.name}:{llm.model}"
        except (AIUnavailableError, ValidationFailed) as exc:
            if not settings.ai_fallback_deterministic:
                raise
            log.info(
                "job_parse_fallback_triggered",
                extra={"reason_code": getattr(exc, "code", "ai_unavailable")},
            )
            fallback_reason = exc.message
            data = parse_job_deterministic(cleaned)
            method = "deterministic_fallback"
            provider_used = "deterministic"

    report = validate_job_evidence(cleaned, data)
    return data, method, provider_used, fallback_reason, report
