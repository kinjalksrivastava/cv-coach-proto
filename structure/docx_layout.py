"""
Word files through the same tree.

A .docx is the easiest of the three sources and the old pipeline made the
most of it the hardest. It flattened every paragraph to a string, dropped the
formatting that says which line is a heading, and then appended every table
cell at the END of the document, so a CV laid out in a table arrived with its
content in an order nobody wrote it in.

Converting to PDF first - the obvious shortcut - is the wrong trade. Word
already records what a PDF makes us infer: whether a run is bold, how far a
paragraph is indented, and whether Word itself considers the paragraph a list
item. Rendering to PDF throws that away and asks us to guess it back from
pixels, and it needs LibreOffice on the server to do it.

Two details carry the layout:

  A TAB is Word's column separator. "Universität St. Gallen, Schweiz\\t09/2023
  - heute" is one line in two fields, exactly like the gap between columns in
  a PDF, and splitting on it is what lets the date be read apart from the
  employer.

  A list paragraph carries no bullet CHARACTER at all - Word draws the glyph
  from the numbering definition. Career Services' own student template is
  built that way, and reading paragraph.text alone reported their canonical
  good example as a CV with no bullet points anywhere.
"""

from __future__ import annotations

import io

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from .layout import Line, Page

# Nominal geometry, consistent rather than real: the tree reads relative
# indents and relative gaps, never absolute positions.
CHAR_WIDTH = 5.0
LINE_HEIGHT = 12.0
DEFAULT_SIZE = 10.5

# What a list paragraph is given so the rest of the pipeline sees a bullet.
LIST_MARKER = "•"


def _is_list_item(paragraph: Paragraph) -> bool:
    """Word's own answer to "is this a bullet", not a guess at the text."""
    style = (getattr(paragraph.style, "name", "") or "").lower()
    if style.startswith("list") or "bullet" in style:
        return True
    try:
        properties = paragraph._p.pPr
        return properties is not None and properties.numPr is not None
    except Exception:
        return False


def _indent_points(paragraph: Paragraph) -> float:
    fmt = paragraph.paragraph_format
    for value in (fmt.left_indent, fmt.first_line_indent):
        if value is not None:
            try:
                return max(0.0, float(value.pt))
            except Exception:
                continue
    return 0.0


def _bold_share(paragraph: Paragraph) -> float:
    total = weighted = 0
    for run in paragraph.runs:
        length = len(run.text)
        if not length:
            continue
        total += length
        if run.bold:
            weighted += length
    return (weighted / total) if total else 0.0


def _size_points(paragraph: Paragraph, fallback: float) -> float:
    for run in paragraph.runs:
        if run.font is not None and run.font.size is not None:
            try:
                return float(run.font.size.pt)
            except Exception:
                continue
    return fallback


def _font_name(paragraph: Paragraph) -> str:
    for run in paragraph.runs:
        if run.font is not None and run.font.name:
            return run.font.name
    return ""


def _body_in_order(document) -> list:
    """
    Paragraphs and tables in the order they appear in the file.

    python-docx exposes the two separately, and reading all the paragraphs
    and then all the tables puts a table-based CV's content in an order that
    exists nowhere in the document.
    """
    from docx.oxml.ns import qn
    out = []
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            out.append(Paragraph(child, document))
        elif child.tag == qn("w:tbl"):
            out.append(Table(child, document))
    return out


def read_docx(file_bytes: bytes) -> list[Page]:
    document = Document(io.BytesIO(file_bytes))
    try:
        default = float(document.styles["Normal"].font.size.pt)
    except Exception:
        default = DEFAULT_SIZE

    page = Page(number=1, width=600.0, height=100_000.0, body_size=default)
    y = 0.0

    def emit(text: str, indent: float, bold: bool, size: float,
             font: str, listed: bool) -> None:
        nonlocal y
        if not text.strip():
            y += LINE_HEIGHT
            return
        if listed:
            text = f"{LIST_MARKER} {text.strip()}"
        cursor = indent
        # A tab is a column break, the same thing a wide gap is in a PDF.
        for field in [f for f in text.split("\t")]:
            if not field.strip():
                cursor += CHAR_WIDTH * 6
                continue
            width = len(field.strip()) * CHAR_WIDTH
            page.lines.append(Line(
                text=field.strip(), page=1, top=y, bottom=y + LINE_HEIGHT * 0.8,
                x0=cursor, x1=cursor + width, size=size, bold=bold,
                fontname=font or "docx",
            ))
            cursor += width + CHAR_WIDTH * 4
        y += LINE_HEIGHT

    for block in _body_in_order(document):
        if isinstance(block, Paragraph):
            emit(block.text, _indent_points(block), _bold_share(block) > 0.6,
                 _size_points(block, default), _font_name(block),
                 _is_list_item(block))
            continue
        # A table row is a row: its cells are the fields of one line, which is
        # what a two-column CV built in Word actually is.
        for row in block.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            seen, unique = set(), []
            for cell in cells:                 # merged cells repeat their text
                if cell and cell not in seen:
                    seen.add(cell)
                    unique.append(cell)
            if unique:
                emit("\t".join(unique), 0.0, False, default, "docx", False)

    left = min((l.x0 for l in page.lines), default=0.0)
    for line in page.lines:
        line.indent = line.x0 - left
    page.column_bounds = [(0.0, page.width)]
    return [page]
