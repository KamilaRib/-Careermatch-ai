"""Deterministic evidence validator ensuring zero fabrication on extracted resume items."""

from __future__ import annotations

import re
import unicodedata

from app.schemas.resume import EvidenceValidationReport, ParsedResumeData

_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Case-folds, strips accents/punctuation noise and collapses whitespace for substring verification."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = stripped.lower()
    cleaned = re.sub(r"[^\w\s@.+/#-]", " ", lowered)
    return _WS_RE.sub(" ", cleaned).strip()


def is_evidence_grounded(raw_text: str, quote: str, fallback_token: str = "") -> bool:
    """Returns True if `quote` (or `fallback_token`) is demonstrably grounded in `raw_text`."""
    norm_raw = _normalize(raw_text)
    if not norm_raw:
        return False

    norm_quote = _normalize(quote)
    if norm_quote and len(norm_quote) >= 3:
        if norm_quote in norm_raw:
            return True
        # Check significant token overlap (>= 75% of tokens with len >= 3 present in raw_text)
        tokens = [t for t in norm_quote.split(" ") if len(t) >= 3]
        if tokens:
            matched = sum(1 for t in tokens if t in norm_raw)
            if matched / len(tokens) >= 0.75:
                return True

    norm_fallback = _normalize(fallback_token)
    if norm_fallback and len(norm_fallback) >= 2 and norm_fallback in norm_raw:
        return True

    return False


def validate_resume_evidence(raw_text: str, data: ParsedResumeData) -> EvidenceValidationReport:
    """Validates every extracted item against `raw_text` and flags unverified items."""
    total = 0
    verified = 0
    warnings: list[str] = []

    for exp in data.experiences:
        total += 1
        anchor = f"{exp.role} {exp.company}".strip()
        ok = is_evidence_grounded(raw_text, exp.evidence_quote, anchor)
        exp.evidence_verified = ok
        if ok:
            verified += 1
        else:
            warnings.append(
                f"Experiência '{anchor or 'sem título'}' não possui comprovação textual direta no documento original."
            )

    for edu in data.education:
        total += 1
        anchor = f"{edu.degree} {edu.institution}".strip()
        ok = is_evidence_grounded(raw_text, edu.evidence_quote, anchor)
        edu.evidence_verified = ok
        if ok:
            verified += 1
        else:
            warnings.append(
                f"Formação '{anchor or 'sem curso'}' não foi localizada literalmente no texto original."
            )

    for cert in data.certifications:
        total += 1
        ok = is_evidence_grounded(raw_text, cert.evidence_quote, cert.name)
        cert.evidence_verified = ok
        if ok:
            verified += 1
        else:
            warnings.append(
                f"Certificação '{cert.name}' não possui evidência textual verificada no original."
            )

    for skill in data.technical_skills:
        total += 1
        ok = is_evidence_grounded(raw_text, skill.evidence_quote, skill.name)
        skill.evidence_verified = ok
        if ok:
            verified += 1
        else:
            warnings.append(
                f"Competência '{skill.name}' não foi encontrada literalmente no texto original."
            )

    for lang in data.languages:
        total += 1
        ok = is_evidence_grounded(raw_text, lang.evidence_quote, lang.language)
        lang.evidence_verified = ok
        if ok:
            verified += 1
        else:
            warnings.append(
                f"Idioma '{lang.language}' não possui evidência textual verificada no original."
            )

    for proj in data.projects:
        total += 1
        ok = is_evidence_grounded(raw_text, proj.evidence_quote, proj.name)
        proj.evidence_verified = ok
        if ok:
            verified += 1
        else:
            warnings.append(
                f"Projeto '{proj.name}' não possui evidência textual verificada no original."
            )

    return EvidenceValidationReport(
        total_items_checked=total,
        verified_items=verified,
        unverified_warnings=warnings,
    )
