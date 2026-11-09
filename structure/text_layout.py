"""
Plain text through the same tree.

A PDF carries its layout in coordinates. Pasted text carries it in spaces: the
indent of a bullet, the run of blanks that right-aligns a date, the empty line
between one job and the next. Less to go on, but the same shapes, so it is
read into the same Rows and handed to the same builder rather than to a second
parser that would drift away from the first.

This path matters as much as the PDF one. A student can paste their CV into
the box instead of uploading it, and tests/layouts.py - the enumeration of
every way an entry can be written, which exists because two bugs on Career
Services' own template came from layouts nobody had tested - is written in
plain text.
"""

from __future__ import annotations

import re

from .layout import Line, Page, Row

# Nominal geometry. Nothing here is real, it only has to be consistent: the
# tree reads relative indents and relative gaps, never absolute positions.
CHAR_WIDTH = 5.0
LINE_HEIGHT = 12.0
BODY_SIZE = 10.0

# Two or more spaces separate fields on a line - the run that right-aligns a
# date or a location. One space is a word space.
FIELD_SPLIT = re.compile(r"[ \t]{2,}")


def read_text(text: str) -> list[Page]:
    """Plain text as a single page of rows, fields split out as columns."""
    page = Page(number=1, width=600.0, height=10_000.0, body_size=BODY_SIZE)
    y = 0.0
    for raw in text.splitlines():
        if not raw.strip():
            # A blank line is the author saying "this block has ended". It is
            # the only vertical spacing plain text has.
            y += LINE_HEIGHT
            continue
        indent = (len(raw) - len(raw.lstrip(" \t"))) * CHAR_WIDTH
        cursor = indent
        for field in FIELD_SPLIT.split(raw.strip()):
            if not field:
                continue
            width = len(field) * CHAR_WIDTH
            page.lines.append(Line(
                text=field, page=1, top=y, bottom=y + LINE_HEIGHT * 0.8,
                x0=cursor, x1=cursor + width,
                size=BODY_SIZE, bold=False, fontname="text",
            ))
            cursor += width + CHAR_WIDTH * 3
        y += LINE_HEIGHT

    left = min((l.x0 for l in page.lines), default=0.0)
    for line in page.lines:
        line.indent = line.x0 - left
    page.column_bounds = [(0.0, page.width)]
    return [page]


def rows_of_text(text: str) -> list[Row]:
    pages = read_text(text)
    from .layout import rows_of
    return rows_of(pages[0])
