"""Resume extraction, deterministic fallback parser and AI orchestration service.

- Uses `upload_guard.py` for multi-layer validation (size, extension, MIME, magic bytes,
  macro blocking, Zip Bomb protection).
- Extracts text in memory from PDF (`PyMuPDF` with automatic `pypdf` fallback), DOCX (`python-docx`)
  and TXT (UTF-8 / Latin-1), discarding raw file bytes immediately after extraction.
- Rejects scanned/image-only PDFs with `ocr_not_available` (HTTP 422).
- Orchestrates structured extraction via the configured `LLMProvider` (Ollama by default,
  or Gemini/OpenAI) and falls back to `parse_resume_deterministic()` when the LLM is unavailable,
  explicitly tagging `extraction_method="deterministic_fallback"` so it is never misrepresented as AI.
"""

from __future__ import annotations

import asyncio
import io
import re

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.ai.prompts.resume_prompts import (
    RESUME_PARSE_SYSTEM_PROMPT,
    build_resume_parse_user_prompt,
)
from app.ai.providers.base import LLMProvider, get_llm_provider
from app.ai.validators.evidence_validator import validate_resume_evidence
from app.core.config import Settings
from app.core.errors import AIUnavailableError, ValidationFailed
from app.core.logging import get_logger
from app.schemas.resume import (
    CertificationItem,
    EducationItem,
    EvidenceValidationReport,
    ExperienceItem,
    ExtractionMethod,
    LanguageItem,
    ParsedResumeData,
    PersonalInfo,
    ProjectItem,
    SkillItem,
)
from app.security.upload_guard import ValidatedUpload

try:
    import fitz as _fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    _fitz = None

log = get_logger("app.services.resume_parser")

MIN_EXTRACTABLE_CHARS = 30

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?(?:9?\d{4}[-\s]?\d{4})"
)
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?", re.IGNORECASE)

_SECTION_HEADERS: dict[str, tuple[str, ...]] = {
    "summary": (
        "resumo",
        "resumo profissional",
        "perfil",
        "perfil profissional",
        "sobre",
        "sobre mim",
        "summary",
        "professional summary",
        "objetivo",
    ),
    "experience": (
        "experiencia",
        "experiência",
        "experiencia profissional",
        "experiência profissional",
        "historico profissional",
        "histórico profissional",
        "atuacao profissional",
        "atuação profissional",
        "work experience",
        "experience",
    ),
    "education": (
        "formacao",
        "formação",
        "formacao academica",
        "formação acadêmica",
        "educacao",
        "educação",
        "education",
    ),
    "skills": (
        "competencias",
        "competências",
        "competencias tecnicas",
        "competências técnicas",
        "habilidades",
        "tecnologias",
        "skills",
        "technical skills",
    ),
    "certifications": (
        "certificacoes",
        "certificações",
        "cursos e certificacoes",
        "cursos e certificações",
        "certifications",
    ),
    "languages": (
        "idiomas",
        "linguas",
        "línguas",
        "languages",
    ),
    "projects": (
        "projetos",
        "projetos relevantes",
        "projects",
    ),
}

_PERIOD_RE = re.compile(
    r"((?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|[01]?\d)?[./\s-]*(?:19|20)\d{2}"
    r"\s*(?:-|–|—|a|até|to)\s*"
    r"(?:atual|presente|present|momento|(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|[01]?\d)?[./\s-]*(?:19|20)\d{2}))",
    re.IGNORECASE,
)


def _normalize_extracted_paragraphs(text: str) -> str:
    """Rejoins soft-wrapped PDF lines within the same paragraph while preserving headers and bullets."""
    out: list[str] = []
    for raw_ln in text.splitlines():
        ln = raw_ln.strip()
        if not ln:
            out.append("")
            continue
        if (
            out
            and out[-1] != ""
            and not _classify_header(ln)
            and not _classify_header(out[-1])
            and not ln.startswith(("-", "•", "*", "–", "—"))
            and "|" not in ln
            and "|" not in out[-1]
            and not _PERIOD_RE.search(ln)
            and not _PERIOD_RE.search(out[-1])
            and not out[-1].endswith((".", ":", ";", "!"))
            and (ln[0].islower() or len(out[-1]) >= 65)
        ):
            out[-1] = f"{out[-1]} {ln}"
        else:
            out.append(ln)
    return "\n".join(out)


def _extract_pdf_text_sync(data: bytes) -> str:
    pages_text: list[str] = []
    if _fitz is not None:
        with _fitz.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                pages_text.append(page.get_text("text") or "")
    else:
        reader = PdfReader(io.BytesIO(data), strict=False)
        for page in reader.pages:
            pages_text.append(page.extract_text() or "")

    raw_joined = "\n\n".join(p.strip() for p in pages_text if p.strip()).strip()
    full_text = _normalize_extracted_paragraphs(raw_joined)
    if len(re.sub(r"\s+", "", full_text)) < MIN_EXTRACTABLE_CHARS:
        raise ValidationFailed(
            "Este PDF parece ser digitalizado (imagem) e não possui texto selecionável. "
            "O serviço de OCR não está habilitado nesta versão; envie um PDF com texto selecionável, "
            "um arquivo DOCX ou cole o texto do currículo.",
            code="ocr_not_available",
        )
    return full_text


def _extract_docx_text_sync(data: bytes) -> str:
    doc = DocxDocument(io.BytesIO(data))
    parts: list[str] = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            parts.append(t)
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(dict.fromkeys(cells)))
    full_text = "\n".join(parts).strip()
    if len(re.sub(r"\s+", "", full_text)) < MIN_EXTRACTABLE_CHARS:
        raise ValidationFailed(
            "O documento DOCX não contém texto suficiente para análise.",
            code="empty_extracted_text",
        )
    return full_text


def _extract_txt_text_sync(data: bytes) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    text = text.strip()
    if len(re.sub(r"\s+", "", text)) < MIN_EXTRACTABLE_CHARS:
        raise ValidationFailed(
            "O arquivo de texto é muito curto para ser processado como currículo.",
            code="empty_extracted_text",
        )
    return text


async def extract_text_from_upload(validated: ValidatedUpload, max_chars: int = 60_000) -> str:
    """Extracts text in a worker thread so the async event loop is never blocked."""
    if validated.kind == "pdf":
        text = await asyncio.to_thread(_extract_pdf_text_sync, validated.data)
    elif validated.kind == "docx":
        text = await asyncio.to_thread(_extract_docx_text_sync, validated.data)
    else:
        text = await asyncio.to_thread(_extract_txt_text_sync, validated.data)

    return text[:max_chars]


def _classify_header(line: str) -> str | None:
    cleaned = re.sub(r"^[\d.#*\-–—•\s]+|[:\s#*]+$", "", line.strip()).lower()
    if not cleaned or len(cleaned) > 45:
        return None
    for sec, aliases in _SECTION_HEADERS.items():
        if cleaned in aliases:
            return sec
    return None


def parse_resume_deterministic(raw_text: str) -> ParsedResumeData:
    """Rule-based deterministic parser used when no LLM is available.

    Never fabricates data: every field and `evidence_quote` is sliced directly from `raw_text`.
    """
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        return ParsedResumeData()

    header_block = "\n".join(lines[:8])
    email_m = _EMAIL_RE.search(raw_text)
    phone_m = _PHONE_RE.search(raw_text)
    linkedin_m = _LINKEDIN_RE.search(raw_text)

    # Candidate name is typically the first non-contact line near the top
    full_name = ""
    for ln in lines[:4]:
        if _classify_header(ln):
            continue
        if "@" in ln or "linkedin.com" in ln.lower():
            continue
        # Remove inline separators if name is on the first line
        candidate = re.split(r"[|•–—]", ln)[0].strip()
        if 2 <= len(candidate.split()) <= 6 and not any(ch.isdigit() for ch in candidate):
            full_name = candidate[:160]
            break

    location = ""
    for ln in lines[:6]:
        loc_m = re.search(
            r"([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+)*\s*[-/,]\s*[A-Z]{2})\b", ln
        )
        if loc_m:
            location = loc_m.group(1).strip()
            break

    personal = PersonalInfo(
        full_name=full_name,
        email=email_m.group(0) if email_m else "",
        phone=phone_m.group(0).strip() if phone_m else "",
        linkedin=linkedin_m.group(0) if linkedin_m else "",
        location=location,
        evidence_quote=header_block[:600],
    )

    sections: dict[str, list[str]] = {k: [] for k in _SECTION_HEADERS}
    current_sec: str | None = None
    for ln in lines[1:]:
        sec = _classify_header(ln)
        if sec is not None:
            current_sec = sec
            continue
        if current_sec is not None:
            sections[current_sec].append(ln)

    summary_text = " ".join(sections["summary"]).strip()[:4000]

    # Experiences
    experiences: list[ExperienceItem] = []
    exp_lines = sections["experience"]
    current_exp: ExperienceItem | None = None
    for ln in exp_lines:
        period_m = _PERIOD_RE.search(ln)
        is_bullet = ln.startswith(("-", "•", "*", "–"))
        if not is_bullet and (period_m or "|" in ln or " — " in ln or " - " in ln):
            if current_exp is not None:
                experiences.append(current_exp)
            period = period_m.group(1) if period_m else ""
            header_wo_period = ln.replace(period, "").strip(" |-–—•,()") if period else ln
            parts = [p.strip() for p in re.split(r"[|—–]| - ", header_wo_period) if p.strip()]
            role = parts[0][:180] if parts else header_wo_period[:180]
            company = parts[1][:180] if len(parts) > 1 else ""
            current_exp = ExperienceItem(
                role=role,
                company=company,
                period=period[:120],
                responsibilities=[],
                achievements=[],
                evidence_quote=ln[:1200],
                evidence_verified=True,
            )
        elif current_exp is not None:
            clean_bullet = ln.lstrip("-•*–— ").strip()
            if clean_bullet:
                current_exp.responsibilities.append(clean_bullet)
                combined = f"{current_exp.evidence_quote} {ln}".strip()
                current_exp.evidence_quote = combined[:1200]
        else:
            current_exp = ExperienceItem(
                role=ln[:180],
                evidence_quote=ln[:1200],
                evidence_verified=True,
            )
    if current_exp is not None:
        experiences.append(current_exp)

    # Education
    education: list[EducationItem] = []
    for ln in sections["education"]:
        clean = ln.lstrip("-•*–— ").strip()
        if not clean:
            continue
        period_m = _PERIOD_RE.search(clean)
        period = period_m.group(1) if period_m else ""
        wo_period = clean.replace(period, "").strip(" |-–—,()") if period else clean
        parts = [p.strip() for p in re.split(r"[|—–]| - ", wo_period) if p.strip()]
        degree = parts[0][:200] if parts else wo_period[:200]
        institution = parts[1][:200] if len(parts) > 1 else ""
        education.append(
            EducationItem(
                degree=degree,
                institution=institution,
                period=period[:120],
                evidence_quote=ln[:600],
                evidence_verified=True,
            )
        )

    # Skills
    skills: list[SkillItem] = []
    seen_skills: set[str] = set()
    for ln in sections["skills"]:
        clean = re.sub(r"^[A-Za-zÀ-ÿ\s]{2,25}:\s*", "", ln.lstrip("-•*–— ").strip())
        for token in re.split(r"[,;|•]", clean):
            name = token.strip()
            if 1 < len(name) <= 60 and name.lower() not in seen_skills:
                seen_skills.add(name.lower())
                skills.append(
                    SkillItem(
                        name=name,
                        category="Técnica",
                        evidence_quote=ln[:600],
                        evidence_verified=True,
                    )
                )

    # Certifications
    certifications: list[CertificationItem] = []
    for ln in sections["certifications"]:
        clean = ln.lstrip("-•*–— ").strip()
        if clean:
            year_m = re.search(r"\b(19|20)\d{2}\b", clean)
            certifications.append(
                CertificationItem(
                    name=clean[:200],
                    year=year_m.group(0) if year_m else "",
                    evidence_quote=ln[:600],
                    evidence_verified=True,
                )
            )

    # Languages
    languages: list[LanguageItem] = []
    for ln in sections["languages"]:
        clean = ln.lstrip("-•*–— ").strip()
        for chunk in re.split(r"[,;|•]", clean):
            item = chunk.strip()
            if not item:
                continue
            parts = [p.strip() for p in re.split(r"[:\-–—()]", item) if p.strip()]
            lang_name = parts[0][:80]
            prof = parts[1][:80] if len(parts) > 1 else ""
            languages.append(
                LanguageItem(
                    language=lang_name,
                    proficiency=prof,
                    evidence_quote=ln[:400],
                    evidence_verified=True,
                )
            )

    # Projects
    projects: list[ProjectItem] = []
    for ln in sections["projects"]:
        clean = ln.lstrip("-•*–— ").strip()
        if clean:
            parts = [p.strip() for p in re.split(r"[:|—–]| - ", clean, maxsplit=1) if p.strip()]
            name = parts[0][:180]
            desc = parts[1][:1000] if len(parts) > 1 else clean[:1000]
            projects.append(
                ProjectItem(
                    name=name,
                    description=desc,
                    evidence_quote=ln[:800],
                    evidence_verified=True,
                )
            )

    return ParsedResumeData(
        personal_info=personal,
        professional_summary=summary_text,
        summary_evidence_quote=summary_text[:1000],
        experiences=experiences,
        education=education,
        certifications=certifications,
        technical_skills=skills,
        languages=languages,
        projects=projects,
    )


async def parse_resume_text(
    raw_text: str,
    settings: Settings,
    *,
    provider: LLMProvider | None = None,
    use_deterministic_only: bool = False,
) -> tuple[ParsedResumeData, ExtractionMethod, str, str | None, EvidenceValidationReport]:
    """Parses resume text via LLMProvider or deterministic fallback and validates textual evidence."""
    cleaned = (raw_text or "").strip()
    if len(re.sub(r"\s+", "", cleaned)) < MIN_EXTRACTABLE_CHARS:
        raise ValidationFailed(
            "O texto do currículo é muito curto para análise (mínimo de 30 caracteres úteis).",
            code="resume_text_too_short",
        )

    fallback_reason: str | None = None
    if use_deterministic_only:
        data = parse_resume_deterministic(cleaned)
        method: ExtractionMethod = "deterministic_fallback"
        provider_used = "deterministic"
    else:
        try:
            llm = provider or get_llm_provider(settings)
            if getattr(llm, "name", "") == "ollama":
                # Hybrid Local AI: deterministic baseline gives instant sub-millisecond extraction
                # of all sections/evidences, while Ollama llama3.2 enriches on CPU within budget.
                baseline = parse_resume_deterministic(cleaned)
                if hasattr(llm, "enrich_resume_fast"):
                    data = await llm.enrich_resume_fast(cleaned, baseline)  # type: ignore[attr-defined]
                else:
                    data = await llm.generate_structured(
                        system_prompt=RESUME_PARSE_SYSTEM_PROMPT,
                        user_prompt=build_resume_parse_user_prompt(cleaned),
                        schema=ParsedResumeData,
                    )
            else:
                data = await llm.generate_structured(
                    system_prompt=RESUME_PARSE_SYSTEM_PROMPT,
                    user_prompt=build_resume_parse_user_prompt(cleaned),
                    schema=ParsedResumeData,
                )
            method = "llm"
            provider_used = f"{llm.name}:{llm.model}"
        except (AIUnavailableError, ValidationFailed) as exc:
            if not settings.ai_fallback_deterministic:
                raise
            log.info(
                "resume_parse_fallback_triggered",
                extra={"reason_code": getattr(exc, "code", "ai_unavailable")},
            )
            fallback_reason = exc.message
            data = parse_resume_deterministic(cleaned)
            method = "deterministic_fallback"
            provider_used = "deterministic"

    report = validate_resume_evidence(cleaned, data)
    return data, method, provider_used, fallback_reason, report
