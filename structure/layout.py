"""
The page as it is laid out, not as a flat string.

A PDF has no structure in it. It says "draw this glyph at this coordinate in
this font", and nothing else. Everything a human uses to see that a line is a
heading - that it is bold, that it is larger, that there is space above it,
that it sits at the left margin while the text under it is indented - is in
those coordinates and in the font of each character.

The old pipeline called page.extract_text(), which throws all of it away, and
then tried to recover the structure by matching the flat text against word
lists: a vocabulary of headings, a list of bullet characters. Anything not on
a list became invisible. That is how a CV full of bullets was reported as
having none, and how a whole education section ended up in no section at all.

This module keeps the evidence. It returns Lines, each carrying where it sits,
how big it is, whether it is bold, and which column it belongs to. Nothing
here decides what anything MEANS - no headings, no entries, no sections. It
only reports what is on the page. Meaning is tree.py's job.
"""

from __future__ import annotations

import io
import statistics
from dataclasses import dataclass, field

import pdfplumber

# Two characters on the same line never differ in 'top' by more than this.
# PDFs place a line's glyphs at slightly different heights - subscripts, a
# different font in the middle of a sentence - so rows have to be gathered
# with a tolerance rather than by exact coordinate.
ROW_TOLERANCE = 3.0

# A gap wider than this many times the usual character width is a column
# break rather than a word space. Measured per page, because font size varies.
COLUMN_GAP_FACTOR = 4.0

# Below this fraction of a page's lines, a candidate column boundary is noise
# - one indented line does not make a column.
MIN_COLUMN_SHARE = 0.25


@dataclass
class Line:
    """One visual line of text, with the evidence needed to read its role."""
    text: str
    page: int
    top: float
    bottom: float
    x0: float
    x1: float
    size: float
    bold: bool
    fontname: str = ""
    # A character standing alone in front of the text, wide enough to be a
    # picture rather than a letter. Whether it IS one cannot be decided here:
    # see _strip_icons_document_wide.
    lead_icon: str = ""
    column: int = 0
    # Set by the reader once the whole page is known.
    space_above: float = 0.0
    indent: float = 0.0

    @property
    def height(self) -> float:
        return self.bottom - self.top

    def __repr__(self) -> str:                               # pragma: no cover
        return (f"Line(p{self.page} top={self.top:.0f} x={self.x0:.0f} "
                f"{'B' if self.bold else ' '} {self.size:.1f} "
                f"{self.text[:40]!r})")


@dataclass
class Page:
    number: int
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)
    body_size: float = 0.0
    column_bounds: list[tuple[float, float]] = field(default_factory=list)
    separate_columns: bool = False


def _is_bold(fontname: str) -> bool:
    name = (fontname or "").lower()
    return "bold" in name or "black" in name or "heavy" in name or "semib" in name


def _rows(chars: list[dict]) -> list[list[dict]]:
    """Gather characters into visual rows, tolerant of small height differences."""
    rows: list[list[dict]] = []
    for char in sorted(chars, key=lambda c: (round(c["top"], 1), c["x0"])):
        if rows and abs(char["top"] - rows[-1][0]["top"]) <= ROW_TOLERANCE:
            rows[-1].append(char)
        else:
            rows.append([char])
    return [sorted(row, key=lambda c: c["x0"]) for row in rows]


def _median_char_width(chars: list[dict]) -> float:
    widths = [c["x1"] - c["x0"] for c in chars if c["x1"] > c["x0"]]
    return statistics.median(widths) if widths else 5.0


def _split_row(row: list[dict], gap: float) -> list[list[dict]]:
    """
    Cut a row wherever the horizontal gap is too wide to be a word space.

    This is what stops "2025 - 2027" in the left column and "University of
    St. Gallen" in the right from arriving as "2025 - 2027University of St.
    Gallen" - the join that currently corrupts the text and hides the layout.
    """
    pieces, current = [], [row[0]]
    for previous, char in zip(row, row[1:]):
        if char["x0"] - previous["x1"] > gap:
            pieces.append(current)
            current = [char]
        else:
            current.append(char)
    pieces.append(current)
    return pieces


def _leading_icon_candidate(chars: list[dict]) -> bool:
    """
    Remove an icon glyph standing in front of a heading.

    CVs built in Canva and Word decorate their headings with a small picture -
    a briefcase, a graduation cap - taken from an icon font. The PDF records
    it as an ordinary letter in the ordinary text font, so "BERUFSERFAHRUNG"
    arrives as "S BERUFSERFAHRUNG" and "ORGANISATIONEN" as "ö ORGANISATIONEN",
    which would be printed back to the student in their own report.

    Nothing about the character says it is a picture - same font, same size.
    What gives it away is how much room it takes: an icon keeps its own
    advance width, so it occupies about twice the space of a real letter
    beside it. That, and standing alone in front of the words, is the test.
    """
    if len(chars) < 5:
        return False
    first, rest = chars[0], chars[1:]
    if len((first.get("text") or "").strip()) != 1:
        return False
    # Space characters are dropped before this point, so the icon is measured
    # by how far the next glyph starts from it, not by a space between them.
    widths = sorted(c["x1"] - c["x0"] for c in rest if c["x1"] > c["x0"])
    if len(widths) < 3:
        return False
    typical = widths[len(widths) // 2]
    if typical <= 0:
        return False

    # Two things have to hold together. The glyph is set apart from the words
    # by a space - letters inside a word are not - and it takes up more room
    # than an ordinary letter. The space alone is not enough, because "A
    # Levels" is a real heading; the width alone is not either, because a
    # capital M is genuinely wide, and testing width on its own turned
    # "München" into "ünchen" and lost the K off "Kellner".
    separated = (rest[0]["x0"] - first["x1"]) > typical * 0.45
    oversized = (first["x1"] - first["x0"]) > typical * 1.4
    return separated and oversized


def _text_of(chars: list[dict], space: float) -> str:
    """Join characters, inserting a space where the PDF left a visible gap."""
    out = []
    for previous, char in zip([None] + chars[:-1], chars):
        if previous is not None and (char.get("_space_before")
                                     or char["x0"] - previous["x1"] > space):
            out.append(" ")
        out.append(char["text"])
    return " ".join("".join(out).split())


def read_pdf(file_bytes: bytes) -> list[Page]:
    """Every page, as lines that still know where they are."""
    pages: list[Page] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for number, raw in enumerate(pdf.pages, start=1):
            # The space characters are dropped for positioning - they have no
            # ink and would skew the median width - but NOT before noting where
            # they were. Re-deriving every space from the gap alone fails on a
            # glyph whose box overhangs the one after it: an "f" swallows the
            # gap, so "Master of Arts" came back as "Master ofArts", "in terms
            # of circular economy" as "in terms ofcircular". The PDF said where
            # the spaces are; there is no reason to guess.
            chars = []
            space_before = False
            for char in raw.chars:
                text = char.get("text", "")
                if not text:
                    continue
                if not text.strip():
                    space_before = True
                    continue
                char["_space_before"] = space_before
                space_before = False
                chars.append(char)
            page = Page(number=number, width=raw.width, height=raw.height)
            if not chars:
                pages.append(page)
                continue

            unit = _median_char_width(chars)
            column_gap = unit * COLUMN_GAP_FACTOR
            # A space inside a line is narrower than a column break. PDFs often
            # omit the space character entirely and rely on the gap, which is
            # why "Memberofthe" and "workfor" come out of extract_text joined.
            word_gap = unit * 0.28

            for row in _rows(chars):
                for piece in _split_row(row, column_gap):
                    icon = (piece[0]["text"]
                            if _leading_icon_candidate(piece) else "")
                    text = _text_of(piece, word_gap)
                    if not text:
                        continue
                    sizes = [c["size"] for c in piece]
                    bold_share = sum(_is_bold(c["fontname"]) for c in piece) / len(piece)
                    page.lines.append(Line(
                        text=text,
                        page=number,
                        top=min(c["top"] for c in piece),
                        bottom=max(c["bottom"] for c in piece),
                        x0=min(c["x0"] for c in piece),
                        x1=max(c["x1"] for c in piece),
                        size=statistics.median(sizes),
                        bold=bold_share > 0.6,
                        fontname=_commonest(c["fontname"] for c in piece),
                        lead_icon=icon,
                    ))

            page.body_size = _body_size(page.lines)
            _assign_columns(page, column_gap)
            _measure_spacing(page)
            pages.append(page)
    _strip_icons_document_wide(pages)
    for page in pages:
        _measure_spacing(page)
    return pages


# A marker has to open this many lines before it is read as a bullet rather
# than as decoration. Three is enough to be a pattern and small enough that a
# short CV still qualifies.
MIN_MARKER_USES = 3


def _strip_icons_document_wide(pages: list[Page]) -> None:
    """
    Remove decorative icons, and only those.

    A heading dressed with a briefcase from an icon font arrives as a single
    wide letter standing in front of the words - "S BERUFSERFAHRUNG". So does
    a Wingdings bullet: good cv 5 prints an arrow in front of 24 lines and
    the file records every one as a plain ">" in Times New Roman. By width
    and spacing the two are identical, and stripping on that test alone
    deleted the CV's entire bullet structure while fixing its headings.

    What separates them is how often the character is used. Decoration on a
    heading appears once or twice, and a different glyph each time; a bullet
    marker opens line after line. So the decision is made once the whole
    document has been read, never per line.
    """
    counts: dict[str, int] = {}
    for page in pages:
        for line in page.lines:
            if line.lead_icon:
                counts[line.lead_icon] = counts.get(line.lead_icon, 0) + 1
    markers = {c for c, n in counts.items() if n >= MIN_MARKER_USES}
    for page in pages:
        for line in page.lines:
            if line.lead_icon and line.lead_icon not in markers:
                line.text = line.text[1:].lstrip()


def _commonest(values) -> str:
    counts: dict[str, int] = {}
    for value in values:
        counts[value or ""] = counts.get(value or "", 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0] if counts else ""


def _body_size(lines: list[Line]) -> float:
    """
    The size ordinary text is set in: the most common size weighted by how
    much text is set in it. Headings are the exception on a page, never the
    rule, so the bulk of the characters are the body.
    """
    if not lines:
        return 0.0
    weighted: dict[float, int] = {}
    for line in lines:
        weighted[round(line.size, 1)] = weighted.get(round(line.size, 1), 0) + len(line.text)
    return max(weighted.items(), key=lambda item: item[1])[0]


def _assign_columns(page: Page, column_gap: float) -> None:
    """
    Group lines into columns by their left edge.

    Deliberately conservative: a left edge only becomes a column if a real
    share of the page's lines start there. A CV with one indented quotation
    has one column, not two.
    """
    if not page.lines:
        return
    starts = sorted(line.x0 for line in page.lines)
    clusters: list[list[float]] = [[starts[0]]]
    for value in starts[1:]:
        if value - clusters[-1][-1] > column_gap:
            clusters.append([value])
        else:
            clusters[-1].append(value)

    threshold = max(2, int(len(page.lines) * MIN_COLUMN_SHARE))
    real = [c for c in clusters if len(c) >= threshold]
    if len(real) < 2:
        page.column_bounds = [(0.0, page.width)]
        return

    bounds = []
    for index, cluster in enumerate(real):
        left = min(cluster)
        right = min(real[index + 1]) if index + 1 < len(real) else page.width
        bounds.append((left, right))
    page.column_bounds = bounds
    for line in page.lines:
        for index, (left, right) in enumerate(bounds):
            if left - 1 <= line.x0 < right:
                line.column = index
                break


def _measure_spacing(page: Page) -> None:
    """
    Vertical gap above each line, and how far it is indented.

    Indent is measured from one origin for the whole page, not from each
    column's own left edge. Normalising per column destroyed the only thing
    indent is for: a bullet sits further right than the entry title above it,
    and if the two happen to fall either side of a detected column boundary,
    per-column measurement reported the bullet as further LEFT. On good cv 6
    that turned 17 bullets into 2, because nothing looked subordinate to
    anything.

    A page read as separate flows is the exception - there each flow really
    does have its own margin, and that is what its lines are indented from.
    """
    if page.separate_columns:
        groups: dict[int, list[Line]] = {}
        for line in page.lines:
            groups.setdefault(line.column, []).append(line)
    else:
        groups = {0: list(page.lines)}

    for lines in groups.values():
        lines.sort(key=lambda l: l.top)
        left = min(l.x0 for l in lines)
        for index, line in enumerate(lines):
            line.indent = line.x0 - left
            line.space_above = (0.0 if index == 0
                                else line.top - lines[index - 1].bottom)


@dataclass
class Row:
    """
    One visual row: everything printed at the same height on the page.

    A CV line is very often two pieces - "TRUSEQ GmbH" at the left margin and
    "München, Deutschland" hard against the right - and those two belong to
    each other. Splitting them apart is what lets us read the date and the
    title separately; keeping them in one row is what stops the date being
    mistaken for a separate entry.

    This is the unit the tree is built from, not the Line.
    """
    pieces: list[Line]

    @property
    def top(self) -> float:
        return min(p.top for p in self.pieces)

    @property
    def bottom(self) -> float:
        return max(p.bottom for p in self.pieces)

    @property
    def left(self) -> Line:
        return min(self.pieces, key=lambda p: p.x0)

    @property
    def right(self) -> Line:
        return max(self.pieces, key=lambda p: p.x0)

    @property
    def text(self) -> str:
        return "   ".join(p.text for p in sorted(self.pieces, key=lambda p: p.x0))

    @property
    def bold(self) -> bool:
        """Bold if the bulk of the row's characters are."""
        total = sum(len(p.text) for p in self.pieces) or 1
        return sum(len(p.text) for p in self.pieces if p.bold) / total > 0.6

    @property
    def size(self) -> float:
        return max(p.size for p in self.pieces)

    @property
    def indent(self) -> float:
        return self.left.indent

    @property
    def x0(self) -> float:
        return self.left.x0

    @property
    def x1(self) -> float:
        return max(p.x1 for p in self.pieces)

    def __repr__(self) -> str:                               # pragma: no cover
        return f"Row(top={self.top:.0f} {'B' if self.bold else ' '} {self.text[:54]!r})"


def _overlap_share(rows: list["Row"]) -> float:
    """
    How often does a row start before the one above it has finished?

    On a page with one flow of text this is zero: lines follow one another
    down the page. It only happens when lines from two independent columns
    have been interleaved into the same sequence, and then it happens a lot.
    It is the symptom that gave away "Russisch (B2)   BERUFSERFAHRUNG" - a
    language level from the sidebar welded to a heading in the main column.

    Measuring the damage is more reliable than predicting it. Column geometry
    looks the same whether the narrow column annotates the wide one (dates
    beside jobs, which must stay paired) or runs beside it (a sidebar, which
    must not). Interleaving tells the two apart by whether it breaks.
    """
    if len(rows) < 4:
        return 0.0
    bad = sum(1 for a, b in zip(rows, rows[1:]) if b.top < a.bottom - ROW_TOLERANCE)
    return bad / (len(rows) - 1)


def rows_of(page: Page) -> list[Row]:
    """
    The page's lines gathered back into visual rows, in reading order.

    Sidebars are the exception this has to survive: a narrow column running
    the full height of the page is its own flow, not the left half of every
    row in the main column. Where the columns do not pair up, each is read
    through to its end before the next one starts.
    """
    if not page.lines:
        return []

    def gather(lines: list[Line]) -> list[Row]:
        out: list[Row] = []
        for line in sorted(lines, key=lambda l: (l.top, l.x0)):
            if out and abs(line.top - out[-1].top) <= ROW_TOLERANCE:
                out[-1].pieces.append(line)
            else:
                out.append(Row(pieces=[line]))
        return out

    merged = gather(page.lines)
    if len(page.column_bounds) < 2 or _overlap_share(merged) <= 0.15:
        return merged

    # The columns do not belong to each other: read each one through to its
    # end before starting the next, the way a person reads a sidebar.
    page.separate_columns = True
    rows: list[Row] = []
    for column in sorted({l.column for l in page.lines}):
        rows += gather([l for l in page.lines if l.column == column])
    return rows


def gap_above(rows: list[Row]) -> list[float]:
    """Vertical white space above each row - the signal that a block has ended."""
    gaps = [0.0]
    for previous, row in zip(rows, rows[1:]):
        gaps.append(row.top - previous.bottom)
    return gaps
