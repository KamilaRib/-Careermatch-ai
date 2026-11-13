from __future__ import annotations

import io
import zipfile

import pytest
from docx import Document
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.security.upload_guard import (
    MAX_PDF_PAGES,
    PayloadTooLargeError,
    sanitize_filename,
    validate_upload_bytes,
)
from tests.conftest import csrf_headers


def _make_pdf(pages: int = 1, text: str = "Currículo de Teste") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for _ in range(pages):
        c.drawString(72, 720, text)
        c.showPage()
    c.save()
    return buf.getvalue()


def _make_docx(text: str = "Experiência profissional") -> bytes:
    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph(text)
    doc.save(buf)
    return buf.getvalue()


def test_valid_pdf_passes() -> None:
    raw = _make_pdf(2)
    res = validate_upload_bytes(raw, "Curriculo Maria.pdf", "application/pdf", max_bytes=1024 * 1024)
    assert res.kind == "pdf"
    assert res.filename == "Curriculo_Maria.pdf"
    assert res.size_bytes == len(raw)


def test_valid_docx_passes() -> None:
    raw = _make_docx()
    res = validate_upload_bytes(
        raw,
        "curriculo.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        max_bytes=1024 * 1024,
    )
    assert res.kind == "docx"


def test_valid_txt_utf8_and_latin1_pass() -> None:
    utf8_bytes = "Currículo João — São Paulo".encode("utf-8")
    r1 = validate_upload_bytes(utf8_bytes, "cv.txt", "text/plain", max_bytes=1024 * 1024)
    assert r1.kind == "txt"

    latin1_bytes = "Currículo José - Conceição".encode("latin-1")
    r2 = validate_upload_bytes(latin1_bytes, "cv.txt", "text/plain", max_bytes=1024 * 1024)
    assert r2.kind == "txt"


def test_rejects_unsupported_extension() -> None:
    with pytest.raises(ValidationFailed) as exc:
        validate_upload_bytes(b"hello", "malicious.exe", "application/octet-stream", max_bytes=1024)
    assert exc.value.code == "unsupported_extension"


def test_rejects_mismatched_mime_type() -> None:
    raw = _make_pdf(1)
    with pytest.raises(ValidationFailed) as exc:
        validate_upload_bytes(raw, "cv.pdf", "text/plain", max_bytes=1024 * 1024)
    assert exc.value.code == "invalid_mime_type"


def test_rejects_spoofed_pdf_magic_bytes() -> None:
    with pytest.raises(ValidationFailed) as exc:
        validate_upload_bytes(b"NOT_A_PDF_FILE", "cv.pdf", "application/pdf", max_bytes=1024 * 1024)
    assert exc.value.code == "invalid_file_signature"


def test_rejects_pdf_with_too_many_pages() -> None:
    raw = _make_pdf(MAX_PDF_PAGES + 1)
    with pytest.raises(ValidationFailed) as exc:
        validate_upload_bytes(raw, "huge.pdf", "application/pdf", max_bytes=5 * 1024 * 1024)
    assert exc.value.code == "pdf_too_many_pages"


def test_rejects_docx_with_vba_macros() -> None:
    base_docx = _make_docx()
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base_docx), "r") as zin, zipfile.ZipFile(buf, "w") as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        zout.writestr("word/vbaProject.bin", b"FAKE_VBA_MACRO_PAYLOAD")

    with pytest.raises(ValidationFailed) as exc:
        validate_upload_bytes(
            buf.getvalue(),
            "macro.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            max_bytes=2 * 1024 * 1024,
        )
    assert exc.value.code == "docx_macros_forbidden"


def test_rejects_docx_zip_bomb_high_ratio() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 5 MB of zeros compresses to a few kilobytes -> ratio > 35x and > 2 MB uncompressed
        zf.writestr("word/document.xml", b"0" * (5 * 1024 * 1024))

    with pytest.raises(ValidationFailed) as exc:
        validate_upload_bytes(
            buf.getvalue(),
            "bomb.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            max_bytes=2 * 1024 * 1024,
        )
    assert exc.value.code == "docx_zip_bomb"


def test_rejects_txt_with_null_bytes() -> None:
    with pytest.raises(ValidationFailed) as exc:
        validate_upload_bytes(b"hello\x00world", "cv.txt", "text/plain", max_bytes=1024)
    assert exc.value.code == "invalid_txt_binary"


def test_rejects_oversized_payload() -> None:
    with pytest.raises(PayloadTooLargeError):
        validate_upload_bytes(b"a" * 2048, "cv.txt", "text/plain", max_bytes=1024)


def test_sanitize_filename_strips_path_traversal() -> None:
    assert sanitize_filename("../../etc/passwd.txt") == "passwd.txt"


def test_streaming_body_limit_blocks_chunked_payload(client: TestClient) -> None:
    headers = csrf_headers(client)
    # Generator forces chunked transfer without a small Content-Length bypass
    def _chunks():
        for _ in range(12):
            yield b"x" * (1024 * 1024)

    r = client.post("/api/v1/sessions/current", content=_chunks(), headers=headers)
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"


def test_invalid_gemini_key_format_reports_warning() -> None:
    s = Settings(_env_file=None, ai_provider="gemini", gemini_api_key="AQ.invalid-token")  # type: ignore[call-arg]
    assert s.ai_configured is False
    assert s.ai_key_warning is not None
    assert "AIza" in s.ai_key_warning


def test_valid_gemini_key_format_is_configured() -> None:
    s = Settings(_env_file=None, ai_provider="gemini", gemini_api_key="AIzaSyFakeKeyForUnitTestOnly12345")  # type: ignore[call-arg]
    assert s.ai_configured is True
    assert s.ai_key_warning is None
