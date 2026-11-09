"""
One entry point: a file or some pasted text, and out comes the tree.

Three readers feed one builder. Which one runs is decided by what arrived,
and nothing downstream of the tree knows or cares which it was:

    .pdf    layout.py       glyph positions, font sizes, weights
    .docx   docx_layout.py  run formatting, indents, Word's own list marks
    text    text_layout.py  indentation and blank lines, for pasted CVs

The point of keeping them separate is that each source knows something the
others do not, and converting between them loses it. A Word file states which
paragraphs are list items; rendering it to PDF to reuse the PDF reader would
throw that away and make us infer it from pixels.
"""

from __future__ import annotations

import os

from . import docx_layout, layout, text_layout
from .tree import Document, build


class Unreadable(Exception):
    """The file could not be read at all - not a parse failure, a read one."""


def read(data: bytes | str, filename: str = "") -> Document:
    """Build the tree from an uploaded file or from pasted text."""
    if isinstance(data, str):
        return build(text_layout.read_text(data))

    suffix = os.path.splitext(filename)[1].lower()
    try:
        if suffix == ".pdf":
            pages = layout.read_pdf(data)
        elif suffix in (".docx", ".docm"):
            pages = docx_layout.read_docx(data)
        else:
            return build(text_layout.read_text(data.decode("utf-8", "replace")))
    except Exception as error:                                   # noqa: BLE001
        raise Unreadable(str(error)) from error

    document = build(pages)
    _note_what_could_not_be_read(document, pages)
    return document


def _note_what_could_not_be_read(document: Document, pages) -> None:
    """
    Say so when the structure could not be read, rather than going quiet.

    A section the parser cannot make sense of used to disappear, and a
    section that disappears is reported as nothing at all - which the student
    reads as approval. Career Services found exactly that twice: a section
    marked Strong because no rule had ever looked at it.

    So the tree carries its own doubts, and the report prints them. "I could
    not read this part of your CV" is a worse answer than reading it and a
    far better one than silence.
    """
    # Rows, not Lines. A row can hold several Lines - a title and the date
    # printed to its right are one line of the CV in two pieces - so counting
    # pieces made every well-parsed document look half-lost.
    text_lines = sum(len(layout.rows_of(page)) for page in pages)
    placed = 0
    for section in _walk(document):
        placed += len(section.items)
        for entry in section.entries:
            placed += 1 + len(entry.bullets) + len(entry.description)
    placed += len(document.preamble)

    if not document.sections:
        document.confident = False
        document.notes.append(
            "no sections could be read from this file, so nothing in it has "
            "been checked section by section")
        return

    unnamed = [s for s in _walk(document) if not s.heading]
    if unnamed:
        document.notes.append(
            f"{len(unnamed)} block(s) were found with no heading that could be "
            f"read; they have been checked, but they cannot be named")

    if text_lines and placed / text_lines < 0.6:
        document.confident = False
        document.notes.append(
            f"only about {placed * 100 // max(1, text_lines)}% of this "
            f"document could be placed into a section; the layout may not "
            f"have been read correctly")


def _walk(document: Document):
    for section in document.sections:
        yield section
        for child in section.subsections:
            yield child
