"""Deterministic hybrid ATS matchmaking engine.

Rules enforced (from `docs/matching-methodology.md` and Megaprompt Section 8):
1. Base category weights:
   - Competências técnicas: 30%
   - Experiência profissional: 25%
   - Requisitos obrigatórios: 20%
   - Formação e certificações: 10%
   - Competências comportamentais: 10%
   - Palavras-chave: 5%
2. No double-counting: each evaluated requirement belongs to exactly one primary scoring
   category (or is evaluated on its own axis without duplicating identical tokens).
3. Weight renormalization: if any category has 0 evaluable items, its weight is redistributed
   proportionally across the applicable categories so active weights always sum to 100%.
4. Match states:
   - `atendido` (credit 1.0): direct or canonical synonym evidence in the confirmed resume.
   - `parcialmente_atendido` (credit 0.5): related technology/ecosystem or partial experience years.
   - `nao_identificado` (credit 0.0): no textual evidence found in the resume. Never framed as
     proof that the candidate lacks the skill—labeled as "não comprovado no currículo".
   - `nao_atendido` (credit 0.0): only when a provable numeric/factual contradiction exists
     (e.g., job demands 8+ years and resume explicitly states fewer total years).
   - `nao_avaliavel` (excluded from denominator): subjective/contextual items that cannot be
     verified from a resume document alone.
5. Explicit eliminatory requirements (`is_eliminatory=True`) that are not `atendido` generate
   a dedicated alert in `eliminatory_alerts`.
"""

from __future__ import annotations

import re
import unicodedata

from app.schemas.job import JobRequirementItem, ParsedJobData
from app.schemas.matching import (
    CategoryScoreItem,
    MatchingResult,
    MatchState,
    RequirementMatchItem,
    ScoreBand,
    ScoringCategoryKey,
)
from app.schemas.resume import ParsedResumeData

BASE_WEIGHTS: dict[ScoringCategoryKey, tuple[str, float]] = {
    "competencias_tecnicas": ("Competências técnicas", 30.0),
    "experiencia_profissional": ("Experiência profissional", 25.0),
    "requisitos_obrigatorios": ("Requisitos obrigatórios", 20.0),
    "formacao_certificacoes": ("Formação e certificações", 10.0),
    "competencias_comportamentais": ("Competências comportamentais", 10.0),
    "palavras_chave": ("Palavras-chave", 5.0),
}

IMPORTANCE_WEIGHTS: dict[str, float] = {
    "obrigatorio": 1.0,
    "desejavel": 0.6,
    "contextual": 0.3,
    "nao_especificado": 0.5,
}

# Canonical skill synonyms and related ecosystems
SKILL_SYNONYMS: dict[str, set[str]] = {
    "python": {"python", "python3", "python 3.12", "py"},
    "fastapi": {"fastapi", "fast api"},
    "postgresql": {"postgresql", "postgres", "psql"},
    "docker": {"docker", "containers", "containerizacao"},
    "kubernetes": {"kubernetes", "k8s"},
    "aws": {"aws", "amazon web services", "ec2", "s3", "lambda"},
    "pytest": {"pytest", "testes automatizados", "unit testing"},
    "git": {"git", "github", "gitlab", "versionamento"},
    "rest api": {"rest", "api rest", "apis rest", "restful"},
    "ci/cd": {"ci/cd", "integracao continua", "github actions", "gitlab ci"},
    "react": {"react", "reactjs", "react.js"},
    "typescript": {"typescript", "ts"},
    "javascript": {"javascript", "js", "es6"},
    "sql": {"sql", "banco de dados relacional", "bancos de dados relacionais"},
    "ingles": {"ingles", "english"},
    "portugues": {"portugues", "portuguese"},
}

# Used strictly to generate advisory recommendations when a required skill is unverified,
# NEVER to grant score credit or treat related skills as evidence of the required skill.
RELATED_SKILLS: dict[str, set[str]] = {
    "kubernetes": {"docker", "aws"},
    "aws": {"docker", "gcp", "azure"},
    "kafka": {"redis", "rabbitmq", "mensageria", "microsservicos"},
    "django": {"python", "fastapi", "flask"},
    "fastapi": {"python", "django", "flask"},
    "postgresql": {"sql", "mysql"},
}


def _norm(text: str) -> str:
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^\w\s/+.#-]", " ", stripped.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _estimate_resume_years(resume: ParsedResumeData, raw_resume_text: str) -> int | None:
    """Extracts explicitly stated years of experience or sums period ranges from the resume."""
    combined = f"{resume.professional_summary}\n{raw_resume_text}"
    m = re.search(r"(\d{1,2})\+?\s*anos?\s+de\s+experi", _norm(combined))
    if m:
        return int(m.group(1))

    years_found: set[int] = set()
    for exp in resume.experiences:
        yrs = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", exp.period)]
        if len(yrs) >= 2:
            for y in range(min(yrs), max(yrs) + 1):
                years_found.add(y)
        elif len(yrs) == 1 and any(w in exp.period.lower() for w in ("atual", "presente", "present")):
            for y in range(yrs[0], 2026 + 1):
                years_found.add(y)
    return len(years_found) if years_found else None


def _build_resume_corpus(resume: ParsedResumeData, raw_resume_text: str) -> list[tuple[str, str]]:
    """Builds `(normalized_text, original_quote)` pairs from the confirmed resume."""
    entries: list[tuple[str, str]] = []
    if resume.professional_summary:
        entries.append((_norm(resume.professional_summary), resume.professional_summary))
    for sk in resume.technical_skills:
        if sk.name:
            quote = sk.evidence_quote or sk.name
            entries.append((_norm(f"{sk.name} {quote}"), f"Competência: {sk.name} ({quote})"))
    for exp in resume.experiences:
        resp_joined = " ".join(exp.responsibilities + exp.achievements)
        block = f"{exp.role} {exp.company} {exp.period} {resp_joined}"
        entries.append((_norm(block), f"Experiência: {exp.role} em {exp.company} ({exp.period})"))
    for edu in resume.education:
        block = f"{edu.degree} {edu.institution} {edu.period}"
        entries.append((_norm(block), f"Formação: {edu.degree} — {edu.institution}"))
    for cert in resume.certifications:
        entries.append((_norm(cert.name), f"Certificação: {cert.name}"))
    for lang in resume.languages:
        block = f"{lang.language} {lang.proficiency}"
        entries.append((_norm(block), f"Idioma: {lang.language} ({lang.proficiency})"))
    for proj in resume.projects:
        block = f"{proj.name} {proj.description} {' '.join(proj.technologies)}"
        entries.append((_norm(block), f"Projeto: {proj.name} — {proj.description}"))
    if raw_resume_text:
        for ln in raw_resume_text.splitlines():
            if ln.strip():
                entries.append((_norm(ln), ln.strip()))
    return entries


def _canonical_tokens_in_text(norm_text: str) -> set[str]:
    found: set[str] = set()
    for canon, aliases in SKILL_SYNONYMS.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", norm_text):
                found.add(canon)
                break
    return found


def _evaluate_single_requirement(
    req: JobRequirementItem,
    scoring_category: ScoringCategoryKey,
    corpus: list[tuple[str, str]],
    resume_canons: set[str],
    resume_years: int | None,
) -> RequirementMatchItem:
    req_norm = _norm(req.name)
    if not req_norm or len(req_norm) < 2:
        return RequirementMatchItem(
            requirement_name=req.name,
            category=scoring_category,
            importance=req.importance,
            is_eliminatory=req.is_eliminatory,
            state="nao_avaliavel",
            credit=0.0,
            job_evidence=req.evidence_quote,
            explanation="Requisito subjetivo ou sem critério verificável por texto.",
        )

    # Experience years requirement check
    if req.min_years is not None:
        if resume_years is not None:
            if resume_years >= req.min_years:
                return RequirementMatchItem(
                    requirement_name=req.name,
                    category=scoring_category,
                    importance=req.importance,
                    is_eliminatory=req.is_eliminatory,
                    state="atendido",
                    credit=1.0,
                    job_evidence=req.evidence_quote,
                    resume_evidence=f"Tempo de experiência comprovado no currículo: ~{resume_years} anos.",
                    explanation=f"A vaga pede {req.min_years} anos e o currículo comprova cerca de {resume_years} anos.",
                )
            if resume_years >= max(1, int(req.min_years * 0.6)):
                return RequirementMatchItem(
                    requirement_name=req.name,
                    category=scoring_category,
                    importance=req.importance,
                    is_eliminatory=req.is_eliminatory,
                    state="parcialmente_atendido",
                    credit=0.5,
                    job_evidence=req.evidence_quote,
                    resume_evidence=f"Tempo identificado no currículo: ~{resume_years} anos.",
                    explanation=(
                        f"A vaga solicita {req.min_years} anos; o currículo registra aproximadamente "
                        f"{resume_years} anos (atendimento parcial)."
                    ),
                )
            return RequirementMatchItem(
                requirement_name=req.name,
                category=scoring_category,
                importance=req.importance,
                is_eliminatory=req.is_eliminatory,
                state="nao_atendido",
                credit=0.0,
                job_evidence=req.evidence_quote,
                resume_evidence=f"Tempo registrado no currículo: ~{resume_years} anos.",
                explanation=(
                    f"A vaga exige {req.min_years} anos, porém o currículo comprova apenas ~{resume_years} anos."
                ),
            )

    # Canonical skill matching (exclude degrees, certifications, and behavioral requirements
    # so related tech ecosystem skills don't falsely satisfy formal certifications)
    is_certification_or_degree = (
        req.category == "competencias_comportamentais"
        or "certificacao" in req_norm
        or "certified" in req_norm
        or "bacharelado" in req_norm
        or "graduacao" in req_norm
    )
    req_canons = _canonical_tokens_in_text(req_norm) if not is_certification_or_degree else set()
    if req_canons:
        matched_canons = req_canons & resume_canons
        if matched_canons == req_canons:
            ev = ""
            for norm_line, quote in corpus:
                if _canonical_tokens_in_text(norm_line) & matched_canons:
                    ev = quote
                    break
            return RequirementMatchItem(
                requirement_name=req.name,
                category=scoring_category,
                importance=req.importance,
                is_eliminatory=req.is_eliminatory,
                state="atendido",
                credit=1.0,
                job_evidence=req.evidence_quote,
                resume_evidence=ev,
                explanation=f"Competência comprovada diretamente no currículo ({', '.join(sorted(matched_canons))}).",
            )
        if matched_canons:
            ev = ""
            for norm_line, quote in corpus:
                if _canonical_tokens_in_text(norm_line) & matched_canons:
                    ev = quote
                    break
            missing = req_canons - matched_canons
            return RequirementMatchItem(
                requirement_name=req.name,
                category=scoring_category,
                importance=req.importance,
                is_eliminatory=req.is_eliminatory,
                state="parcialmente_atendido",
                credit=0.5,
                job_evidence=req.evidence_quote,
                resume_evidence=ev,
                explanation=(
                    f"Atende parte das tecnologias ({', '.join(sorted(matched_canons))}), "
                    f"mas não há evidência no currículo para: {', '.join(sorted(missing))}."
                ),
            )
        # Specific technical skill not present in the resume (related technologies are NEVER
        # accepted as proof of a distinct unverified skill, e.g., Docker/AWS != Kubernetes)
        return RequirementMatchItem(
            requirement_name=req.name,
            category=scoring_category,
            importance=req.importance,
            is_eliminatory=req.is_eliminatory,
            state="nao_identificado",
            credit=0.0,
            job_evidence=req.evidence_quote,
            resume_evidence="",
            explanation=(
                "Não identificado no texto do currículo. Experiência em tecnologias correlatas "
                "não substitui a comprovação direta desta competência."
            ),
        )

    # Token overlap matching for education, behavioral and general requirements
    stop = {"de", "da", "do", "em", "com", "para", "ou", "os", "as", "um", "uma", "no", "na", "por", "conhecimento", "experiencia", "dominio", "solida"}
    tokens = [t for t in req_norm.split() if len(t) >= 3 and t not in stop]
    if not tokens:
        return RequirementMatchItem(
            requirement_name=req.name,
            category=scoring_category,
            importance=req.importance,
            is_eliminatory=req.is_eliminatory,
            state="nao_avaliavel",
            credit=0.0,
            job_evidence=req.evidence_quote,
            explanation="Requisito genérico não avaliável isoladamente.",
        )

    best_ratio = 0.0
    best_quote = ""
    for norm_line, quote in corpus:
        hits = sum(1 for t in tokens if t in norm_line)
        ratio = hits / len(tokens)
        if ratio > best_ratio:
            best_ratio = ratio
            best_quote = quote

    if best_ratio >= 0.7:
        state: MatchState = "atendido"
        credit = 1.0
        expl = "Requisito comprovado por evidência textual no currículo."
    elif best_ratio >= 0.4:
        state = "parcialmente_atendido"
        credit = 0.5
        expl = "Correspondência parcial encontrada no histórico do currículo."
    else:
        state = "nao_identificado"
        credit = 0.0
        best_quote = ""
        expl = (
            "Não identificado no texto do currículo. Caso você possua essa experiência ou competência, "
            "inclua evidências reais na etapa de otimização."
        )

    return RequirementMatchItem(
        requirement_name=req.name,
        category=scoring_category,
        importance=req.importance,
        is_eliminatory=req.is_eliminatory,
        state=state,
        credit=credit,
        job_evidence=req.evidence_quote,
        resume_evidence=best_quote,
        explanation=expl,
    )


def _assign_primary_scoring_category(req: JobRequirementItem) -> ScoringCategoryKey:
    """Assigns each requirement to a single primary scoring category to prevent double counting."""
    if req.category == "experiencia_profissional":
        return "experiencia_profissional"
    if req.category in {"formacao_certificacoes", "idiomas"}:
        return "formacao_certificacoes"
    if req.category == "competencias_comportamentais":
        return "competencias_comportamentais"
    if req.importance == "obrigatorio" and req.category != "competencias_tecnicas":
        return "requisitos_obrigatorios"
    if req.category == "competencias_tecnicas" and req.importance == "obrigatorio":
        # Split mandatory technical requirements: multi-word statements go to mandatory, atomic tech tokens to technical
        if len(req.name.split()) > 3:
            return "requisitos_obrigatorios"
        return "competencias_tecnicas"
    return "competencias_tecnicas"


def classify_score_band(score: int) -> tuple[ScoreBand, str]:
    if score >= 80:
        return "alta_compatibilidade", "Alta compatibilidade"
    if score >= 60:
        return "boa_compatibilidade", "Boa compatibilidade"
    if score >= 40:
        return "compatibilidade_parcial", "Compatibilidade parcial"
    return "baixa_compatibilidade", "Baixa compatibilidade"


def calculate_matching(
    resume: ParsedResumeData,
    job: ParsedJobData,
    *,
    raw_resume_text: str = "",
) -> MatchingResult:
    """Deterministic calculation of compatibility score, category breakdown, strengths and gaps."""
    corpus = _build_resume_corpus(resume, raw_resume_text)
    full_resume_norm = " ".join(n for n, _ in corpus)
    resume_canons = _canonical_tokens_in_text(full_resume_norm)
    resume_years = _estimate_resume_years(resume, raw_resume_text)

    matches: list[RequirementMatchItem] = []
    seen_names: set[str] = set()

    for req in job.requirements:
        norm_name = _norm(req.name)
        if not norm_name or norm_name in seen_names:
            continue
        seen_names.add(norm_name)
        cat_key = _assign_primary_scoring_category(req)
        item_match = _evaluate_single_requirement(
            req, cat_key, corpus, resume_canons, resume_years
        )
        matches.append(item_match)

    # Evaluate Keywords category (5%) from job.keywords / job.technologies without duplicating requirement items
    keyword_tokens = list(dict.fromkeys([*job.keywords, *job.technologies, *job.languages]))
    for kw in keyword_tokens:
        kw_norm = _norm(kw)
        if not kw_norm:
            continue
        synthetic_req = JobRequirementItem(
            name=kw,
            category="competencias_tecnicas",
            importance="obrigatorio",
            evidence_quote=f"Palavra-chave da vaga: {kw}",
        )
        kw_match = _evaluate_single_requirement(
            synthetic_req, "palavras_chave", corpus, resume_canons, resume_years
        )
        matches.append(kw_match)

    # Group evaluable matches by category
    by_cat: dict[ScoringCategoryKey, list[RequirementMatchItem]] = {
        k: [] for k in BASE_WEIGHTS
    }
    for m in matches:
        if m.state != "nao_avaliavel":
            by_cat[m.category].append(m)

    active_base_sum = sum(
        base_w for k, (_, base_w) in BASE_WEIGHTS.items() if len(by_cat[k]) > 0
    )

    category_scores: list[CategoryScoreItem] = []
    total_weighted = 0.0

    for key, (label, base_w) in BASE_WEIGHTS.items():
        items = by_cat[key]
        if not items or active_base_sum == 0:
            category_scores.append(
                CategoryScoreItem(
                    key=key,
                    label=label,
                    base_weight_pct=base_w,
                    normalized_weight_pct=0.0,
                    applicable=False,
                    score=0.0,
                    weighted_contribution=0.0,
                    evaluated_count=0,
                    matched_count=0,
                    partial_count=0,
                )
            )
            continue

        norm_w = round((base_w / active_base_sum) * 100.0, 2)
        weighted_num = 0.0
        weighted_den = 0.0
        matched_c = 0
        partial_c = 0
        for it in items:
            imp_w = IMPORTANCE_WEIGHTS.get(it.importance, 0.5)
            weighted_num += it.credit * imp_w
            weighted_den += imp_w
            if it.state == "atendido":
                matched_c += 1
            elif it.state == "parcialmente_atendido":
                partial_c += 1

        cat_score = round((weighted_num / weighted_den) * 100.0, 1) if weighted_den > 0 else 0.0
        contrib = round((cat_score * norm_w) / 100.0, 2)
        total_weighted += contrib

        category_scores.append(
            CategoryScoreItem(
                key=key,
                label=label,
                base_weight_pct=base_w,
                normalized_weight_pct=norm_w,
                applicable=True,
                score=cat_score,
                weighted_contribution=contrib,
                evaluated_count=len(items),
                matched_count=matched_c,
                partial_count=partial_c,
            )
        )

    overall_score = max(0, min(100, round(total_weighted)))
    band, band_label = classify_score_band(overall_score)

    non_kw_matches = [m for m in matches if m.category != "palavras_chave"]
    matched_keywords = list(
        dict.fromkeys(m.requirement_name for m in matches if m.state == "atendido")
    )
    partial_keywords = list(
        dict.fromkeys(m.requirement_name for m in matches if m.state == "parcialmente_atendido")
    )
    unverified_requirements = list(
        dict.fromkeys(
            m.requirement_name
            for m in non_kw_matches
            if m.state in {"nao_identificado", "nao_atendido"}
        )
    )
    eliminatory_alerts = [
        f"Requisito eliminatório não comprovado integralmente: '{m.requirement_name}' ({m.state})."
        for m in non_kw_matches
        if m.is_eliminatory and m.state != "atendido"
    ]

    strengths = [
        f"{m.requirement_name}: {m.explanation}"
        for m in non_kw_matches
        if m.state == "atendido"
    ][:6]

    gaps = [
        f"{m.requirement_name} ({m.importance}): {m.explanation}"
        for m in non_kw_matches
        if m.state in {"nao_identificado", "parcialmente_atendido", "nao_atendido"}
    ][:6]

    recommendations: list[str] = []
    if unverified_requirements:
        recommendations.append(
            "Revise os requisitos marcados como 'não identificado': se você já utilizou alguma dessas "
            f"competências ({', '.join(unverified_requirements[:4])}) em projetos reais, adicione a evidência "
            "verdadeira nas suas experiências."
        )
    # Generate advisory recommendations from related skills WITHOUT treating them as evidence or credit
    for m in non_kw_matches:
        if m.state == "nao_identificado":
            req_canons = _canonical_tokens_in_text(_norm(m.requirement_name))
            for rc in sorted(req_canons):
                related_found = sorted(RELATED_SKILLS.get(rc, set()) & resume_canons)
                if related_found:
                    recommendations.append(
                        f"Para '{m.requirement_name}' (não identificado no currículo), constam tecnologias "
                        f"correlatas ({', '.join(related_found)}) que não substituem a evidência exigida — "
                        f"caso possua vivência real em '{m.requirement_name}', explicite-a no currículo."
                    )
                    break
    if partial_keywords:
        recommendations.append(
            "Detalhe melhor os itens parcialmente atendidos "
            f"({', '.join(partial_keywords[:3])}) no resumo e nas responsabilidades."
        )
    recommendations.append(
        "Utilize o gerador de Currículo ATS para alinhar a terminologia das suas experiências reais com as palavras-chave da vaga, sem inventar qualificações."
    )

    return MatchingResult(
        overall_score=overall_score,
        band=band,
        band_label=band_label,
        category_scores=category_scores,
        requirement_matches=non_kw_matches,
        matched_keywords=matched_keywords,
        partial_keywords=partial_keywords,
        unverified_requirements=unverified_requirements,
        eliminatory_alerts=eliminatory_alerts,
        strengths=strengths,
        gaps=gaps,
        recommendations=recommendations,
    )
