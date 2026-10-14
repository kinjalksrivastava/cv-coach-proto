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
from guardrails import headings as heading_lookup

MIN_CHARS = 120  # confidence gate threshold
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB cap, matches the requirements doc


class ExtractionResult:
    """
    `meta` carries the document facts that only the FILE knows - page count,
    fonts, whether the layout uses tables, whether images are embedded. The
    format check in the feedback report is built from these rather than guessed
    from the text, because a model reading extracted text genuinely cannot see
    how many pages there are or which font was used.
    """

    def __init__(self, ok: bool, text: str = "", error: str = "", meta: dict | None = None):
        self.ok = ok
        self.text = text
        self.error = error
        self.meta = meta or {}


# pdfplumber decides where a word ends from the gap between two characters, and
# its default tolerance of 3 points is wider than the inter-word gap in a tightly
# set font. A LaTeX CV in Charter came out as "TeachingFellow,NewYorkUniversity"
# - every space in the document gone, which silently broke every rule that reads
# a word boundary. Narrowing the tolerance is not safe as a blanket default: on a
# loosely tracked font it splits words instead. So the default is tried first and
# only replaced when the result is visibly space-starved, and then only by a
# candidate that is not full of one-character fragments.
WORD_GAP_TOLERANCES = (2.0, 1.5)
# Two thresholds, deliberately far apart. A re-read is only triggered by a page
# that is plainly broken (this CV came out at 0.016), and the densest real CV in
# the samples sits at 0.067 - well clear of it. The replacement then has to be
# properly spaced, not marginally better, or the default stands.
BROKEN_SPACE_SHARE = 0.04   # below this, the spaces are missing, not merely few
GOOD_SPACE_SHARE = 0.08     # ordinary prose runs near 0.15
MAX_FRAGMENT_SHARE = 0.12   # one-character tokens, the sign of over-splitting


def _space_share(text: str) -> float:
    return text.count(" ") / len(text) if text else 1.0


def _fragment_share(text: str) -> float:
    tokens = text.split()
    if not tokens:
        return 1.0
    return sum(1 for t in tokens if len(t) == 1) / len(tokens)


def _page_text(page) -> str:
    """The page's text, re-read at a narrower word gap if the spaces are missing."""
    default = page.extract_text() or ""
    if _space_share(default) >= BROKEN_SPACE_SHARE:
        return default
    for tolerance in WORD_GAP_TOLERANCES:
        try:
            candidate = page.extract_text(x_tolerance=tolerance) or ""
        except Exception:
            continue
        if (_space_share(candidate) >= GOOD_SPACE_SHARE
                and _fragment_share(candidate) <= MAX_FRAGMENT_SHARE):
            return candidate
    return default


def _extract_pdf(file_bytes: bytes) -> tuple[str, dict]:
    text_parts, fonts = [], set()
    image_count, table_count = 0, 0
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text_parts.append(_page_text(page))
            for char in page.chars:
                name = char.get("fontname") or ""
                # PDF font names are usually subset-tagged, e.g. "ABCDEF+Arial-Bold".
                fonts.add(name.split("+")[-1].split("-")[0].split(",")[0])
            image_count += len(page.images or [])
            try:
                table_count += len(page.find_tables())
            except Exception:
                pass  # table detection is best-effort; never fail extraction over it
    meta = {
        "source": "pdf",
        "page_count": page_count,
        "fonts": sorted(f for f in fonts if f),
        "image_count": image_count,
        "table_count": table_count,
    }
    return "\n".join(text_parts), meta


def _is_word_list_item(paragraph) -> bool:
    """
    Is this paragraph one of Word's bullet- or number-list items?

    Word stores the bullet as paragraph FORMATTING, not as a character, so
    `paragraph.text` comes back without it. Career Services' own student CV
    template is built that way, and the tool read it as a CV with no bullet
    points anywhere - its canonical good example, told its bullets were missing.
    Most students who upload a .docx will have used the same list button.
    """
    style = (getattr(paragraph.style, "name", "") or "").lower()
    if style.startswith("list") or "bullet" in style:
        return True
    try:
        properties = paragraph._p.pPr
        return properties is not None and properties.numPr is not None
    except Exception:
        return False


def _extract_docx(file_bytes: bytes) -> tuple[str, dict]:
    doc = Document(io.BytesIO(file_bytes))
    # The bullet is put back as an ordinary character, so everything downstream
    # sees the same shape it would in a PDF.
    parts = [("- " + p.text.strip()) if (_is_word_list_item(p) and p.text.strip())
             else p.text
             for p in doc.paragraphs]
    fonts = set()
    for paragraph in doc.paragraphs:
        for run in paragraph.runs:
            if run.font is not None and run.font.name:
                fonts.add(run.font.name)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    try:
        image_count = len(doc.inline_shapes)
    except Exception:
        image_count = 0
    meta = {
        "source": "docx",
        # Word doesn't store a page count that survives extraction - it's a
        # rendering property. Left as None rather than guessed, so the format
        # check can say "couldn't determine" instead of inventing a number.
        "page_count": None,
        "fonts": sorted(fonts),
        "image_count": image_count,
        "table_count": len(doc.tables),
    }
    return "\n".join(parts), meta


def extract_text(file_bytes: bytes, filename: str) -> ExtractionResult:
    if len(file_bytes) > MAX_SIZE_BYTES:
        return ExtractionResult(
            ok=False,
            error=f"File exceeds the 10MB size cap ({filename}). Please upload a smaller file.",
        )

    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    meta: dict = {}
    try:
        if ext == "pdf":
            raw, meta = _extract_pdf(file_bytes)
        elif ext == "docx":
            raw, meta = _extract_docx(file_bytes)
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

    # Icon fonts map to the Unicode private use area, and a CV with a little
    # glyph beside each heading arrives here as "\uf0b7 BERUFSERFAHRUNG". Nothing
    # legitimate on a CV lives in that range, so it comes out before anything
    # else looks at the text. The count is kept: a document full of them is one
    # whose author should be told the icons do not survive a parse.
    raw, icon_lines = heading_lookup.strip_private_use(raw)
    meta["icon_lines"] = icon_lines
    meta["char_count"] = len(raw.strip())
    return ExtractionResult(ok=True, text=raw, meta=meta)
