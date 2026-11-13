"""Multi-layer upload security guard for resume documents (PDF, DOCX, TXT).

Protections implemented:
1. Streaming size cap (`read_upload_bounded`) defending against chunked uploads without Content-Length.
2. Filename sanitization and strict extension allowlist (`.pdf`, `.docx`, `.txt`).
3. Binary magic-bytes signature verification:
   - PDF must start with `%PDF-` and pass structural check (`PyMuPDF` page count <= MAX_PDF_PAGES).
   - DOCX must start with PK ZIP signature (`PK\\x03\\x04`), contain `word/document.xml`,
     have no macro payloads (`vbaProject.bin`, `.bin` macros), and respect anti-Zip-Bomb limits
     (total uncompressed size <= MAX_DOCX_UNCOMPRESSED_BYTES, compression ratio <= MAX_ZIP_RATIO,
     member count <= MAX_ZIP_ENTRIES).
   - TXT must not contain null bytes (`\\x00`) and must decode cleanly as UTF-8 or Latin-1.
"""

from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Literal

from fastapi import UploadFile
from pypdf import PdfReader

from app.core.errors import AppError, ValidationFailed

try:
    import fitz as _fitz  # PyMuPDF (requires VC++ runtime on Windows)
except ImportError:  # pragma: no cover - fallback when native DLL is missing on host OS
    _fitz = None

AllowedKind = Literal["pdf", "docx", "txt"]

ALLOWED_EXTENSIONS: dict[str, AllowedKind] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
}

ALLOWED_MIMES: dict[AllowedKind, set[str]] = {
    "pdf": {"application/pdf", "application/x-pdf", "application/octet-stream"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    "txt": {"text/plain", "application/octet-stream"},
}

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"

MAX_PDF_PAGES = 30
MAX_DOCX_UNCOMPRESSED_BYTES = 25 * 1024 * 1024  # 25 MB uncompressed XML ceiling
MAX_ZIP_RATIO = 35.0
MAX_ZIP_ENTRIES = 250
READ_CHUNK_SIZE = 64 * 1024

FORBIDDEN_DOCX_ENTRIES = (
    "vbaproject.bin",
    "vbadata.xml",
    "activeX",
    "oleObject",
)


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    kind: AllowedKind
    content_type: str
    size_bytes: int
    data: bytes


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str | None) -> str:
    raw = os.path.basename((filename or "").strip().replace("\\", "/"))
    if not raw or raw in {".", ".."}:
        raise ValidationFailed("Nome de arquivo inválido.", code="invalid_filename")
    stem, ext = os.path.splitext(raw)
    safe_stem = _SAFE_NAME_RE.sub("_", stem).strip("._") or "curriculo"
    safe_ext = ext.lower()
    return f"{safe_stem[:80]}{safe_ext}"


async def read_upload_bounded(upload: UploadFile, max_bytes: int) -> bytes:
    """Reads an UploadFile in chunks, aborting immediately if size exceeds max_bytes."""
    buf = bytearray()
    while True:
        chunk = await upload.read(READ_CHUNK_SIZE)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise PayloadTooLargeError("Arquivo excede o tamanho máximo permitido.")
    if len(buf) == 0:
        raise ValidationFailed("O arquivo enviado está vazio.", code="empty_file")
    return bytes(buf)


def _validate_pdf_bytes(data: bytes) -> None:
    if not data.startswith(PDF_MAGIC):
        raise ValidationFailed(
            "Assinatura do arquivo inválida: o arquivo não é um PDF válido.",
            code="invalid_file_signature",
        )
    try:
        if _fitz is not None:
            with _fitz.open(stream=data, filetype="pdf") as doc:
                is_encrypted = bool(doc.is_encrypted)
                page_count = doc.page_count
        else:
            reader = PdfReader(io.BytesIO(data), strict=False)
            is_encrypted = bool(reader.is_encrypted)
            page_count = len(reader.pages)

        if is_encrypted:
            raise ValidationFailed(
                "O PDF está protegido por senha e não pode ser processado.",
                code="encrypted_pdf",
            )
        if page_count == 0:
            raise ValidationFailed("O PDF não possui páginas.", code="empty_pdf")
        if page_count > MAX_PDF_PAGES:
            raise ValidationFailed(
                f"O PDF excede o limite de {MAX_PDF_PAGES} páginas para um currículo.",
                code="pdf_too_many_pages",
            )
    except ValidationFailed:
        raise
    except Exception as exc:
        raise ValidationFailed(
            "Não foi possível ler a estrutura do arquivo PDF.",
            code="corrupted_pdf",
        ) from exc


def _validate_docx_bytes(data: bytes) -> None:
    if not data.startswith(ZIP_MAGIC):
        raise ValidationFailed(
            "Assinatura do arquivo inválida: o arquivo não é um DOCX válido.",
            code="invalid_file_signature",
        )
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
    except zipfile.BadZipFile as exc:
        raise ValidationFailed("Arquivo DOCX corrompido ou inválido.", code="corrupted_docx") from exc

    if len(infos) > MAX_ZIP_ENTRIES:
        raise ValidationFailed(
            "Estrutura interna do DOCX excede o número máximo de entradas permitidas.",
            code="docx_zip_bomb",
        )

    names_lower = [i.filename.lower() for i in infos]
    if "word/document.xml" not in names_lower:
        raise ValidationFailed(
            "O arquivo enviado não possui a estrutura de um documento Word (.docx).",
            code="invalid_docx_structure",
        )

    for name in names_lower:
        if any(forbidden.lower() in name for forbidden in FORBIDDEN_DOCX_ENTRIES):
            raise ValidationFailed(
                "Arquivos DOCX com macros ou conteúdo ativo não são permitidos.",
                code="docx_macros_forbidden",
            )

    total_uncompressed = sum(i.file_size for i in infos)
    if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
        raise ValidationFailed(
            "Conteúdo descomprimido do DOCX excede o limite de segurança.",
            code="docx_zip_bomb",
        )

    compressed_size = max(len(data), 1)
    if (total_uncompressed / compressed_size) > MAX_ZIP_RATIO and total_uncompressed > 2 * 1024 * 1024:
        raise ValidationFailed(
            "Taxa de compressão suspeita detectada no arquivo DOCX.",
            code="docx_zip_bomb",
        )


def _validate_txt_bytes(data: bytes) -> None:
    if b"\x00" in data:
        raise ValidationFailed(
            "O arquivo TXT contém bytes binários inválidos.",
            code="invalid_txt_binary",
        )
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            data.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise ValidationFailed(
                "Não foi possível decodificar o arquivo de texto.",
                code="invalid_txt_encoding",
            ) from exc


def validate_upload_bytes(
    data: bytes,
    filename: str | None,
    content_type: str | None,
    max_bytes: int,
) -> ValidatedUpload:
    if len(data) == 0:
        raise ValidationFailed("O arquivo enviado está vazio.", code="empty_file")
    if len(data) > max_bytes:
        raise PayloadTooLargeError("Arquivo excede o tamanho máximo permitido.")

    safe_name = sanitize_filename(filename)
    _, ext = os.path.splitext(safe_name)
    kind = ALLOWED_EXTENSIONS.get(ext.lower())
    if kind is None:
        raise ValidationFailed(
            "Formato não suportado. Envie um arquivo PDF, DOCX ou TXT.",
            code="unsupported_extension",
        )

    mime = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    if mime and mime not in ALLOWED_MIMES[kind]:
        raise ValidationFailed(
            f"Tipo MIME '{mime}' incompatível com a extensão '{ext}'.",
            code="invalid_mime_type",
        )

    if kind == "pdf":
        _validate_pdf_bytes(data)
    elif kind == "docx":
        _validate_docx_bytes(data)
    else:
        _validate_txt_bytes(data)

    return ValidatedUpload(
        filename=safe_name,
        kind=kind,
        content_type=mime,
        size_bytes=len(data),
        data=data,
    )


async def validate_upload_file(upload: UploadFile, max_bytes: int) -> ValidatedUpload:
    data = await read_upload_bounded(upload, max_bytes=max_bytes)
    return validate_upload_bytes(
        data=data,
        filename=upload.filename,
        content_type=upload.content_type,
        max_bytes=max_bytes,
    )
