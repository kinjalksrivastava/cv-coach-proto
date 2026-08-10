"""
File-to-text extraction with a confidence gate.

Per the requirements doc: PDF and DOCX only, one file per upload, and
a failed or near-empty extraction must stop the flow and ask for a
re-upload rather than proceeding to feedback. It must never claim to
judge layout/formatting, since only text is available downstream.

Photo stripping is implicit here too: only .extract_text()-style text
is ever pulled out, images are never read, so no photo bytes ever
leave this module.
"""

import io

import pdfplumber
from docx import Document

MIN_CHARS = 120  # confidence gate threshold
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB cap, matches the requirements doc


class ExtractionResult:
    def __init__(self, ok: bool, text: str = "", error: str = ""):
        self.ok = ok
        self.text = text
        self.error = error


def _extract_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def extract_text(file_bytes: bytes, filename: str) -> ExtractionResult:
    if len(file_bytes) > MAX_SIZE_BYTES:
        return ExtractionResult(
            ok=False,
            error=f"File exceeds the 10MB size cap ({filename}). Please upload a smaller file.",
        )

    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    try:
        if ext == "pdf":
            raw = _extract_pdf(file_bytes)
        elif ext == "docx":
            raw = _extract_docx(file_bytes)
        else:
            return ExtractionResult(
                ok=False,
                error=f"Unsupported file type '.{ext}'. Please upload a PDF or DOCX file.",
            )
    except Exception as e:
        return ExtractionResult(
            ok=False,
            error=f"Could not parse '{filename}' ({e.__class__.__name__}). "
            "The file may be corrupted or password-protected. Please re-upload.",
        )

    if len(raw.strip()) < MIN_CHARS:
        return ExtractionResult(
            ok=False,
            error=(
                f"Extraction returned very little usable text from '{filename}' "
                "(possibly a scanned or image-based file — this prototype has no "
                "OCR fallback yet). Please re-upload a text-based PDF or DOCX."
            ),
        )

    return ExtractionResult(ok=True, text=raw)
