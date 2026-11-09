"""
Rows into a document: sections, the entries in them, the bullets under those.

layout.py reports what is on the page and refuses to interpret it. This is
where interpretation happens, and it reads the page the way a person does:

  a heading   is set larger than the body, or in bold capitals, with white
              space above it
  an entry    is a job, a degree or an activity - it carries dates, or it sits
              in bold at the section's own left margin
  a bullet    is indented under an entry, whatever character introduces it
  a list item is a line in a section that has no entries at all, which is what
              a languages or skills section is made of

None of that consults a vocabulary. "ZUSÄTZLICHE INFORMATIONEN" is a heading
because it is 11pt bold with 12pt of air above it on a 9pt page, not because
the word is on a list - which is the whole point, because it was not.

Two properties the old parser did not have:

  Nothing is lost. Every row ends up in a section, and every row in a section
  ends up in an entry or in the section's own items. A row that cannot be
  placed is reported, not dropped, because silence is how a CV came to be
  marked Strong on sections nobody had read.

  It says when it is unsure. A document whose structure could not be read
  confidently says so, so the report can tell the student rather than guess.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

import re

from guardrails.dates import RANGE_RE as DATE_RANGE

from . import layout

from guardrails import headings as heading_lookup

# A single date, where a CV gives one rather than a range: "2027", "Sep 2023",
# "09/2024". bad cv 5 anchors three of its education entries on a bare year,
# and anchoring only on ranges lost them into the entry above.
SINGLE_DATE = re.compile(
    r"^(?:(?:19|20)\d{2}"
    r"|(?:0?[1-9]|1[0-2])[./](?:19|20)\d{2}"
    r"|(?:Jan|Feb|M[a\u00e4]r|Apr|Mai|May|Jun|Jul|Aug|Sep|O[ck]t|Nov|De[cz])"
    r"[a-z]*\.?\s*(?:19|20)\d{2})$", re.IGNORECASE)

# A heading is set at least this much larger than the body text.
LARGER_THAN_BODY = 0.4

# White space above a row, as a multiple of the body text size, that marks the
# start of something new rather than the next line of the same thing.
BLOCK_GAP = 1.6

# A heading is short. Six words is generous - "SKILLS, ENGAGEMENTS & INTERESSEN"
# is four.
MAX_HEADING_WORDS = 7

# Indent beyond the entry's own left edge that makes a row subordinate to it.
SUBORDINATE_INDENT = 4.0

# How close to the right-hand edge of the text a line has to end before the
# line below it counts as the rest of it rather than something new. Generous,
# because the last word before a wrap can be long.
MEASURE_SLACK = 0.06

# Characters a bullet may be introduced by, used only as corroboration. The
# old parser depended on this list and went blind when a CV used a round dot
# it did not contain; here indentation decides and the glyph merely confirms.
BULLET_GLYPHS = "-–—•·*▪■●○◦‣→▸▹►⁃∙◆❖➢✓»«"

# Glyphs are not enough on their own. A Wingdings arrow has no Unicode point
# of its own in the file: good cv 5 prints ➢ in front of 24 of its lines and
# the PDF records every one of them as a plain ASCII ">" set in Times New
# Roman. No list of bullet characters will ever contain the right entry for
# that, because the right entry is whatever the substituted font happened to
# land on.
#
# So the markers are learned per document, the same way the heading style is.
# A character that opens a run of lines, always followed by a space, and is
# not a letter or a digit, is what this CV uses for a bullet - whatever it is.
MIN_MARKER_USES = 3


# A place is not a description of what the student did - and it is recognised
# by WHERE IT SITS, not by what it is called.
#
# A two-column CV prints the city hard against the right margin, so the row
# under an entry title is often nothing but the location. Counted as
# description it makes a bare entry look like a described one, and on Serena's
# CV that is exactly what happened: UNIVERSA and START Global have no bullets
# and nothing written under them - her complaint was "It shows Organisationen
# as strong, even though the person has not added any details or bullets to
# their experiences" - and reading "St. Gallen, Schweiz" as detail would have
# put the section straight back to Strong.
#
# The first two attempts at this used word lists: capitalised-looking words,
# then a list of countries. Both were wrong for the same reason every word
# list in this codebase has been wrong. The first ate "Hygienestandards,
# Einarbeitung neuer Mitarbeitenden" because German capitalises its nouns;
# the second could never cover Mumbai, Lagos or Kleinbösingen.
#
# Position settles it and needs no vocabulary at all. On that CV the entry
# titles start at x=43 and real description at x=43.9, while the location
# lines start at x=472. A line that begins in the right-hand half of the
# section is in the right-hand COLUMN: a place, a date, a city - whatever it
# says, in whatever language, it is a field and not a sentence about the work.
#
# Such lines are still kept and still shown to the model, because where the
# student worked is worth knowing. They simply do not count as detail.
RIGHT_COLUMN_SHARE = 0.5


def _in_the_right_column(row: layout.Row, left: float, right: float) -> bool:
    if right <= left:
        return False
    return (row.x0 - left) / (right - left) > RIGHT_COLUMN_SHARE


@dataclass
class Entry:
    """One job, degree or activity, with whatever sits under it."""
    title: str
    dates: str = ""
    bullets: list[str] = field(default_factory=list)
    description: list[str] = field(default_factory=list)

    # Lines that sat in the right-hand column: a city, a place, a date field.
    # Kept so the model still sees where the student worked, but they say
    # nothing about the work, so they are not detail.
    asides: list[str] = field(default_factory=list)

    # The same lines again, in the order they appear on the page, each
    # tagged "bullet", "line" or "aside". The lists above are what the rules
    # count; this is what the model is shown, because printing every
    # description line before every bullet put the second half of a
    # sentence above the first half of it.
    content: list[tuple[str, str]] = field(default_factory=list)

    @property
    def is_bare(self) -> bool:
        """Nothing at all is said about what this was.

        A right-hand-column line does not count, which is why asides are kept
        out of `description`: "St. Gallen, Schweiz" under an entry title is
        where, not what, and counting it as detail put Serena's ORGANISATIONEN
        section back to Strong with two entries that say nothing.
        """
        return not (self.bullets or self.description)

    @property
    def has_detail(self) -> bool:
        return not self.is_bare


@dataclass
class Section:
    heading: str | None
    entries: list[Entry] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    reason: str = ""
    # A section can be divided again: "SKILLS, ENGAGEMENTS & INTERESSEN" holds
    # Fremdsprachenkenntnisse, Engagements and Interessen beneath it, and each
    # wants judging on its own terms - languages on levels, engagements on
    # what was done. Read as entries of the parent they are three activities
    # with no description, which is a finding the CV did not earn.
    subsections: list["Section"] = field(default_factory=list)

    @property
    def has_entries(self) -> bool:
        return bool(self.entries)


@dataclass
class Document:
    sections: list[Section] = field(default_factory=list)
    sub_style: tuple | None = None
    # Does this CV print a marker in front of its bullets? Decided once for
    # the whole document, because a CV is consistent about it and the answer
    # changes what an indented line means. See marks_its_bullets().
    marked_bullets: bool = True
    preamble: list[str] = field(default_factory=list)
    unplaced: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    confident: bool = True


def _words(text: str) -> int:
    return len(text.split())


def _mostly_capitals(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 3:
        return False
    return sum(c.isupper() for c in letters) / len(letters) > 0.8


# A date inside brackets is part of a sentence, not the date of an entry:
# "Leiterin einer Ministrantengruppe (2017-2024), nach einem Freiwilligenjahr"
# is one line of description, and reading its bracketed years as an entry's
# dates split a single activity into three.
BRACKETED = re.compile(r"\([^()]*\)")


def _has_dates(text: str) -> bool:
    return bool(DATE_RANGE.search(text))


def _dates_outside_brackets(text: str) -> bool:
    """
    Dates that belong to this entry, ignoring dates inside a sentence.

    "Analyst, Beispiel AG (09/2022 - 08/2024)" states the entry's dates: the
    bracket closes the line. "Leiterin einer Ministrantengruppe (2017-2024),
    nach einem Freiwilligenjahr" does not: the sentence carries on past it,
    and reading those years as an entry's dates split one activity into three.
    Position, not punctuation.
    """
    if DATE_RANGE.search(BRACKETED.sub(" ", text)):
        return True
    stripped = text.rstrip()
    for match in BRACKETED.finditer(stripped):
        if match.end() >= len(stripped) - 1 and DATE_RANGE.search(match.group(0)):
            return True
    return False


def _ran_to_the_margin(previous: layout.Row | None, measure: float) -> bool:
    """
    Did the line above fill its measure, so that this one is its remainder?

    A line only wraps because the one before it ran out of room. That is the
    general case of the thing punctuation can only sometimes show: "Assisted
    the placement team in the fundraising of a EUR 250m fund using" / "PowerBi,
    conducted a benchmarking exercise" is one bullet, and nothing in the text
    of the second line says so - it opens on a capital letter like any new
    bullet would.

    Getting this wrong splits one bullet into two, and the report counts
    bullets and quotes them back, so the student would be told they have more
    and shorter points than they wrote.
    """
    if previous is None or measure <= 0:
        return False
    # A row carrying a right-aligned field - a date, a location - reaches the
    # right edge because it was pushed there, not because the sentence ran
    # out of room. Treating it as a wrapped line glued the first line of a
    # job's description onto its title, and the job then read as having no
    # description at all.
    if len(previous.pieces) > 1:
        return False
    return previous.x1 >= measure * (1 - MEASURE_SLACK)


def _continues(text: str, previous: str) -> bool:
    """
    Is this row the rest of the row above, wrapped onto a second line?

    A wrapped line starts in the middle of a sentence: lower case, or a
    closing bracket, or straight after a comma left hanging above it. Reading
    one as a new entry turned a single degree into two, the second of them
    beginning "Gallen), Universität St. Gallen".
    """
    if not text or not previous:
        return False
    if _starts_with_glyph(text) or _word_bullet(text):
        return False
    head = text.lstrip()[:1]
    if head and (head.islower() or head in ")]},;"):
        return True
    # A bracket opened above and not closed there is the clearest case: the
    # rest of it has to be on this line. "... Bachelor in BWL, Universität St."
    # / "Gallen), Universität St. Gallen" is one degree, not two.
    if previous.count("(") > previous.count(")") and ")" in text:
        return True
    return previous.rstrip().endswith((",", "-", "/", "&", "und", "and"))


def _anchors_entry(row: layout.Row) -> bool:
    """
    Does this row begin a job, a degree or an activity?

    A date range is the strongest signal and the common case. A lone date in
    the left-hand field is the other one: a CV laid out as "2027 | Peking
    University" is giving the date of a single event, and reading only ranges
    dropped those rows into whatever entry came before them.
    """
    if _dates_outside_brackets(row.text):
        return True
    pieces = sorted(row.pieces, key=lambda p: p.x0)
    if len(pieces) < 2:
        return False
    # Either end of the row. A CV that puts its dates on the left - "2027 |
    # Peking University" - was the case this was written for, but bad cv 10
    # puts them on the right - "Accounting Intern        Aug2025" - and
    # checking only the left-hand piece found a job title there and said no.
    # Three of that CV's five jobs were swallowed into the description of the
    # one above them, and a reader of the report would never learn they exist.
    return bool(SINGLE_DATE.match(pieces[0].text.strip())
                or SINGLE_DATE.match(pieces[-1].text.strip()))


_LEARNED: set[str] = set()


def _starts_with_glyph(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped or stripped[1:2] not in " \t":
        return False
    return stripped[0] in BULLET_GLYPHS or stripped[0] in _LEARNED


def _word_bullet(text: str) -> bool:
    """Word's outline levels two and three print a Courier 'o' as the marker."""
    stripped = text.lstrip()
    return (stripped[:2] in ("o ", "O ")
            and stripped[2:3].isupper())


def _style_of(row: layout.Row, body: float) -> tuple:
    """
    How this row is set: the combination a CV uses consistently for one kind
    of line. Size is bucketed to a quarter point because PDFs record 10.9969
    where the author typed 11.
    """
    family = ""
    if row.pieces:
        name = (row.pieces[0].fontname or "").split("+")[-1]
        family = name.split("-")[0].split(",")[0]
    return (round(row.size * 4) / 4, row.bold, _mostly_capitals(row.text), family)


def _eligible(row: layout.Row) -> bool:
    """Could this row be a heading at all, before style is considered?"""
    if not row.text.strip():
        return False
    if _words(row.text) > MAX_HEADING_WORDS or _has_dates(row.text):
        return False
    if _starts_with_glyph(row.text) or _word_bullet(row.text):
        return False
    # A heading is one field. "Trust Square     Zurich, Switzerland" is a job.
    return len(row.pieces) == 1


def heading_style(rows: list[layout.Row], gaps: list[float], body: float,
                  exclude: tuple | None = None,
                  floor: float = 2.5) -> tuple[tuple | None, str]:
    """
    Which style does this CV use for its section headings?

    There is no list of permitted headings here and no threshold tuned to one
    document. The observation is simply that a CV is internally consistent: it
    sets every section heading the same way, that way is visibly different
    from body text, there are a handful of them, and they are spread down the
    page. Whatever that style turns out to be - 13pt roman on one CV, 8.5pt
    bold capitals on another, bold-at-body-size on a third - it is the style
    that best fits that description.

    This is what replaces the heading vocabulary. A CV headed ARBEITS- &
    FÜHRUNGSERFAHRUNGEN, ATIVIDADES EXTRACURRICULARES or anything a student
    invents next is read the same way, because the question asked is never
    "do I know this word".
    """
    if not rows:
        return None, ""
    typical = _typical_gap(gaps)
    counts: dict[tuple, list[int]] = {}
    for index, row in enumerate(rows):
        if _eligible(row):
            counts.setdefault(_style_of(row, body), []).append(index)

    body_style_bold = _body_is_bold(rows)
    best, best_score, best_why = None, 0.0, ""
    for style, where in counts.items():
        if not 2 <= len(where) <= 15:
            continue
        if exclude is not None and style == exclude:
            continue
        size, bold, caps, _family = style
        score, why = 0.0, []
        if size >= body + LARGER_THAN_BODY:
            score += 2.5
            why.append("larger than the body text")
        if bold and not body_style_bold:
            score += 1.5
            why.append("bold")
        if caps:
            score += 1.5
            why.append("in capitals")
        air = statistics.mean(gaps[i] for i in where)
        if air >= typical * 2:
            score += 1.5
            why.append("with space above")
        elif air >= typical * 1.4:
            score += 0.75
            why.append("with space above")
        # Headings are spread through the document, not clustered in a corner.
        spread = (max(where) - min(where)) / max(1, len(rows) - 1)
        if spread > 0.45:
            score += 1.0
        # Two headings is a thin claim; five or six is a CV.
        if 3 <= len(where) <= 9:
            score += 0.5
        if score > best_score:
            best, best_score, best_why = style, score, ", ".join(why)

    if best_score < floor:
        return None, ""
    return best, best_why


def structural_headings(rows: list[layout.Row], gaps: list[float],
                        body: float) -> set[int]:
    """
    Headings found by what they DO, for a CV that gives no visual clue.

    bad cv 4 sets its whole page in one font at one size with even spacing:
    "Berufserfahrung" is printed exactly like the jobs beneath it. Plain
    pasted text is the same case - no size, no weight, nothing but position.

    What still holds is the job a heading does. It is short, it carries no
    dates, it sits at the left margin, and the thing immediately after it is
    an entry. A line that does all four, several times down one document, is
    a heading however it happens to be set.
    """
    if not rows:
        return set()
    base = min(r.indent for r in rows)
    found = set()
    for index, row in enumerate(rows):
        if not _eligible(row) or row.indent > base + SUBORDINATE_INDENT:
            continue
        following = rows[index + 1:index + 3]
        if not following:
            continue
        if not any(_anchors_entry(r) for r in following):
            continue
        # The row above must not itself be part of an entry: a heading starts
        # a block, it does not sit in the middle of one.
        if index and (_starts_with_glyph(rows[index - 1].text)
                      or rows[index - 1].indent > base + SUBORDINATE_INDENT):
            found.add(index)
            continue
        if index == 0 or gaps[index] >= _typical_gap(gaps):
            found.add(index)
    return found if len(found) >= 2 else set()


def learn_markers(rows: list[layout.Row]) -> set[str]:
    """Characters this CV uses to introduce a bullet, found by counting."""
    counts: dict[str, int] = {}
    for row in rows:
        text = row.text.lstrip()
        if len(text) < 3 or text[1:2] not in (" ", "\t"):
            continue
        mark = text[0]
        if mark.isalnum() or mark in "\"'(":
            continue
        counts[mark] = counts.get(mark, 0) + 1
    return {m for m, n in counts.items() if n >= MIN_MARKER_USES}


def marks_its_bullets(rows: list[layout.Row]) -> bool:
    """
    Does this CV put a marker in front of its bullets?

    It matters because the alternative reading of an indented line is that it
    is description, or the rest of the line above. Counting every indented
    row as a bullet reported 27 bullets on a CV that prints one, and 46 on a
    CV that prints 28 - inflating exactly the measure the report leans on.

    A CV answers this question for itself. Where markers are used they are
    used throughout, so if the document prints a handful, an unmarked
    indented line is not a bullet. Where none are printed, indentation is the
    only thing left and a consistent deeper indent is what a bullet is.
    """
    marked = sum(1 for r in rows
                 if _starts_with_glyph(r.text) or _word_bullet(r.text))
    return marked >= 3


def _is_employer_style(rows: list[layout.Row], style: tuple | None,
                       body: float) -> bool:
    """
    Is this the style the CV uses for employers rather than for sub-headings?

    An employer printed above its role looks exactly like a sub-heading: a
    short bold line with no dates on it. What gives it away is what comes
    next. A sub-heading introduces a group; an employer introduces one dated
    role, immediately, every time.

    Without this the second style tier on good cv 2 was "UniCredit Group,
    Munich, Germany" and its two neighbours, so WORK EXPERIENCE was split
    into three sub-sections of one entry each - four real sections reported
    as eight. Over-splitting is worse than missing a heading: the student
    reads a report about sections their CV does not have.
    """
    if style is None:
        return False
    where = [i for i, row in enumerate(rows)
             if _eligible(row) and _style_of(row, body) == style]
    if not where:
        return False
    followed = sum(1 for i in where
                   if i + 1 < len(rows) and _anchors_entry(rows[i + 1]))
    return followed / len(where) >= 0.5


def _typical_gap(gaps: list[float]) -> float:
    """The ordinary gap between one line and the next within a block."""
    real = [g for g in gaps if g > 0]
    if not real:
        return 1.0
    return max(0.5, statistics.median(real))


def _body_is_bold(rows: list[layout.Row]) -> bool:
    """Some CVs are set in bold throughout; then bold says nothing."""
    if not rows:
        return False
    weight = sum(len(r.text) for r in rows if r.bold)
    return weight / max(1, sum(len(r.text) for r in rows)) > 0.6


def is_heading(row: layout.Row, gap: float, body: float) -> str:
    """
    A single row judged on its own, with no document to compare it to.

    Kept for the case where style detection found nothing to go on, and as the
    fallback for a row that is unmistakable by itself: set clearly larger than
    everything around it.
    """
    if not _eligible(row):
        return ""
    if row.size >= body + LARGER_THAN_BODY and (row.bold or _mostly_capitals(row.text)):
        return "larger than the body text"
    return ""


# A heading that did not fit its column, put back together.
#
# A narrow sidebar wraps its headings: "PERSÖNLICHE DATEN" is printed as
# "PERSÖNLICHE" on one line and "DATEN" on the next, and "BERUFLICHE
# ERFAHRUNG" the same way. Read as two rows they are two headings, neither of
# which means anything - and the cost is not only a bad section list. The
# personal-details block is removed by MATCHING that heading, so a wrapped
# "PERSÖNLICHE DATEN" stopped the block being dropped as a block and left the
# date of birth, civil status and address to be caught one pattern at a time.
# Career Services asked for the whole block to go precisely so that a field
# nobody anticipated could not survive.
#
# The rule is deliberately narrow: join two adjacent rows only when the first
# means nothing on its own AND the two together are a heading we know. Two
# real headings sitting next to each other can never be merged, because the
# first of them resolves.
_WRAP_MAX_WORDS = 3


def _wrapped_heading(first: layout.Row, second: layout.Row,
                     gap: float, body: float) -> bool:
    if first.bold != second.bold or abs(first.size - second.size) > 0.6:
        return False
    # Measured against the HEADING's own size, not the body's. On exp cv bad 1
    # the body is 6pt and the sidebar headings are 10pt, so the ordinary
    # leading between two lines of one heading is 8.6 - already more than the
    # body size, and the first version of this test read it as a blank line and
    # refused to join. A real blank line is nearer twice the leading.
    if gap > max(first.size, second.size) * 1.3:
        return False
    one, two = first.text.strip(), second.text.strip()
    if not one or not two:
        return False
    if len(one.split()) > _WRAP_MAX_WORDS or len(two.split()) > _WRAP_MAX_WORDS:
        return False
    if heading_lookup.identify(one) is not None:
        return False                          # a heading in its own right
    return heading_lookup.identify(f"{one} {two}") is not None


def _rejoin_wrapped_headings(rows: list[layout.Row], gaps: list[float],
                             body: float) -> tuple[list, list]:
    out_rows: list[layout.Row] = []
    out_gaps: list[float] = []
    index = 0
    while index < len(rows):
        row = rows[index]
        if (index + 1 < len(rows)
                and _wrapped_heading(row, rows[index + 1], gaps[index + 1], body)):
            merged = layout.Row(pieces=row.pieces + rows[index + 1].pieces)
            out_rows.append(merged)
            out_gaps.append(gaps[index])
            index += 2
            continue
        out_rows.append(row)
        out_gaps.append(gaps[index])
        index += 1
    return out_rows, out_gaps


def _collect(pages: list[layout.Page]) -> tuple[list[layout.Row], list[float], float]:
    """Every row of the document in reading order, with the gap above each."""
    rows: list[layout.Row] = []
    gaps: list[float] = []
    sizes: list[tuple[float, int]] = []
    for page in pages:
        page_rows = layout.rows_of(page)
        page_gaps = layout.gap_above(page_rows)
        # The first row of a later page has no meaningful gap above it: the
        # page break is not white space the author chose.
        if page_rows and rows:
            page_gaps[0] = BLOCK_GAP * (page.body_size or 10.0)
        rows += page_rows
        gaps += page_gaps
        sizes.append((page.body_size, len(page_rows)))
    body = max(sizes, key=lambda s: s[1])[0] if sizes else 10.0
    rows, gaps = _rejoin_wrapped_headings(rows, gaps, body)
    return rows, gaps, body


def build(pages: list[layout.Page]) -> Document:
    """The document as a tree. Nothing is discarded."""
    rows, gaps, body = _collect(pages)
    document = Document()
    if not rows:
        document.confident = False
        document.notes.append("no text could be read from this file")
        return document

    global _LEARNED
    _LEARNED = learn_markers(rows)
    document.marked_bullets = marks_its_bullets(rows)
    style, why = heading_style(rows, gaps, body)
    sub_style = None
    if style is not None:
        # The next most distinctive way this CV sets a short, undated line.
        # Scored lower than a heading, because a sub-heading is by definition
        # the quieter of the two.
        sub_style, _sub_why = heading_style(rows, gaps, body, exclude=style,
                                            floor=2.0)
        if sub_style == style or _is_employer_style(rows, sub_style, body):
            sub_style = None
    document.sub_style = sub_style
    if style is None:
        where = structural_headings(rows, gaps, body)
        if where:
            document.notes.append(
                "headings read from position: a short undated line introducing "
                "dated entries")
            marks = ["introduces the entries below it" if i in where else ""
                     for i in range(len(rows))]
            return _assemble(rows, gaps, body, marks, document)
    if style is not None:
        marks = [why if (_eligible(row) and _style_of(row, body) == style) else ""
                 for row in rows]
        document.notes.append(f"headings read as: {why}")
    else:
        marks = [is_heading(row, gap, body) for row, gap in zip(rows, gaps)]
    if not any(marks):
        # A CV can be perfectly well structured and have no headings at all -
        # bad cv 5 puts its dates in a left column and separates education,
        # activities and languages by white space alone. Blocking on the gaps
        # recovers exactly those three.
        document.notes.append(
            "no headings were found; blocks were read from the spacing instead")
        return _blocks_from_gaps(rows, gaps, body, document)

    return _assemble(rows, gaps, body, marks, document)


def _assemble(rows, gaps, body, marks, document: Document) -> Document:
    """Cut the document at its headings and fill each section."""
    if not any(marks):
        return _blocks_from_gaps(rows, gaps, body, document)
    # Everything before the first heading is usually the name and contact
    # block. Usually - good cv 2 has its EDUCATION heading destroyed in the
    # file itself, arriving as "( A I >" in a 7.5pt Arial that nothing else
    # on the page uses, and its three degrees then sit above every heading
    # the parser can see. Dropping them as preamble lost a quarter of the CV
    # and reported the student as having no education at all.
    #
    # So the preamble is only a preamble if it holds nothing that looks like
    # an entry. Where it does, it becomes a section whose heading is unknown,
    # which is honest and leaves the rules something to work on.
    first = marks.index(next(m for m in marks if m))
    head_rows = list(zip(rows[:first], gaps[:first]))
    dated = [row for row, _ in head_rows if _anchors_entry(row)]
    if len(dated) >= 2:
        opening = Section(heading=None,
                          reason="entries above the first heading this file "
                                 "still carries")
        _fill(opening, head_rows, body, document.sub_style,
              document.marked_bullets)
        if opening.entries:
            document.sections.append(opening)
            document.notes.append(
                "entries were found above the first readable heading; that "
                "section's heading could not be read from the file")
        else:
            document.preamble = [r.text for r, _ in head_rows]
    else:
        document.preamble = [r.text for r, _ in head_rows]

    current: Section | None = None
    buffer: list[tuple[layout.Row, float]] = []
    for row, gap, mark in zip(rows[first:], gaps[first:], marks[first:]):
        if mark:
            if current is not None:
                _fill(current, buffer, body, document.sub_style,
                      document.marked_bullets)
            current = Section(heading=row.text, reason=mark)
            document.sections.append(current)
            buffer = []
        else:
            buffer.append((row, gap))
    if current is not None:
        _fill(current, buffer, body, document.sub_style, document.marked_bullets)
    _promote_real_sections(document)
    return document


def _promote_real_sections(document: Document) -> None:
    """
    A sub-heading that is really a section of its own is lifted out.

    Sub-headings are found by style: the second most distinctive way a CV sets
    a short line. On exp cv bad 1 that style caught AUSBILDUNG, which was then
    nested inside BERUFLICHE ERFAHRUNG - Education filed as a sub-heading of
    Work Experience. Nothing downstream can recover from that: the report asks
    for the entries under "BERUFLICHE ERFAHRUNG" and gets the seven that are
    directly under it, while five sit in a child nobody looked in.

    Style cannot tell the two apart, but the vocabulary can: Education, Work
    Experience and the rest are sections wherever they appear. A sub-heading
    the lookup does not recognise - an employer, a programme name - stays
    where it is, which is what keeps "TWININGSOVO | MÄRZ 2023-" nested under
    the job it belongs to.
    """
    for section in list(document.sections):
        keep = []
        for child in section.subsections:
            entry = heading_lookup.identify((child.heading or "").strip())
            if entry is None:
                keep.append(child)
                continue
            where = document.sections.index(section)
            document.sections.insert(where + 1, child)
        section.subsections = keep


def _blocks_from_gaps(rows, gaps, body, document: Document) -> Document:
    """Sections delimited by white space, for a CV that prints no headings."""
    section = Section(heading=None, reason="a block separated by white space")
    document.sections.append(section)
    buffer: list[tuple[layout.Row, float]] = []
    for row, gap in zip(rows, gaps):
        if buffer and gap >= BLOCK_GAP * 2 * body:
            _fill(section, buffer, body)
            section = Section(heading=None, reason="a block separated by white space")
            document.sections.append(section)
            buffer = []
        buffer.append((row, gap))
    _fill(section, buffer, body)
    document.sections = [s for s in document.sections if s.entries or s.items]
    return document


def _fill(section: Section, buffer: list[tuple[layout.Row, float]], body: float,
          sub_style: tuple | None = None, marked: bool = True) -> None:
    """Fill a section, dividing it first if it carries sub-headings."""
    if sub_style is not None:
        marks = [i for i, (row, _) in enumerate(buffer)
                 if _eligible(row) and _style_of(row, body) == sub_style]
        if len(marks) >= 2:
            before = buffer[:marks[0]]
            if before:
                _fill_flat(section, before, body, marked)
            for position, start in enumerate(marks):
                end = marks[position + 1] if position + 1 < len(marks) else len(buffer)
                child = Section(heading=buffer[start][0].text,
                                reason="a sub-heading within this section")
                _fill_flat(child, buffer[start + 1:end], body, marked)
                section.subsections.append(child)
            return
    _fill_flat(section, buffer, body, marked)


# Sections whose entries are titled and carry no dates by nature.
TITLED_UNDATED_CATEGORIES = {"Publications & Research", "Projects"}


def _titled_without_dates(buffer: list[tuple[layout.Row, float]],
                          body: float, marked: bool,
                          heading: str | None) -> list[int]:
    """
    Entry titles in a section that carries no dates at all.

    A research paper, a publication and most student projects are titled and
    undated, and the rule above - no dates, therefore a list - filed the title
    and its own bullets side by side as items, so nothing was an entry and no
    entry-level check ran on any of it.

    The distinction a languages list cannot fake is DETAIL. "German: native"
    has nothing underneath it; a paper has two bullets saying what was done.
    So this only applies where the section actually contains bullets, and the
    title is the row that introduces them - recognised by being set in a style
    the bulleted rows do not share, which on one CV is bold at body size and
    on another is a larger size. The style is read from the section itself,
    never assumed.

    Returns the buffer positions that start an entry, or [] to leave the
    section as a flat list.
    """
    # Only where a titled, undated entry is what the section is FOR. The first
    # version asked whether the section contained bullets, and bad cv 2 showed
    # that is not enough: "Core Competences" lists "Technical skills" and
    # "Personal skills" each with bulleted skills under them, which is a list
    # with bullets, not two entries - and it invented two entries and five
    # achievement bullets on a CV whose truth is four entries and none.
    #
    # A publication, a research paper and a project are titled and undated by
    # nature. A skills list, a languages list and an interests list are not,
    # however they are punctuated. The heading says which, so the heading
    # decides.
    if heading is None or heading not in TITLED_UNDATED_CATEGORIES:
        return []
    rows = [row for row, _ in buffer]
    bullets = [i for i, row in enumerate(rows)
               if _starts_with_glyph(row.text) or _word_bullet(row.text)]
    if len(bullets) < 2:
        return []                      # no detail: it is a list after all
    plain = {i for i in range(len(rows))} - set(bullets)
    if not plain:
        return []
    # The style the bulleted rows are set in is the section's ordinary style.
    ordinary = {_style_of(rows[i], body) for i in bullets}
    candidates = [i for i in sorted(plain)
                  if _style_of(rows[i], body) not in ordinary]
    if not candidates:
        return []
    # A title has to introduce something. One that leads nowhere is a stray
    # line, and treating it as an entry would invent an entry with no content.
    starts = [i for i in candidates if any(j > i for j in bullets)]
    # Consecutive title rows are one wrapped title, not two entries.
    merged: list[int] = []
    for i in starts:
        if merged and i == merged[-1] + 1:
            continue
        merged.append(i)
    return merged if len(merged) >= 2 else []


def _fill_flat(section: Section, buffer: list[tuple[layout.Row, float]],
               body: float, marked: bool = True) -> None:
    """
    Sort a section's rows into entries and the lines under them.

    An entry is anchored on dates where there are any, because that is what a
    job or a degree almost always carries and a bullet almost never does. Where
    a section has no dates anywhere it is a list - languages, skills, interests
    - and its rows are items, not bare entries. That distinction is what stops
    "German: native" being reported as an activity with no description.
    """
    if not buffer:
        return
    base = min(row.indent for row, _ in buffer)
    # The section's own right-hand edge, for telling a right-column field from
    # a line of description. Measured here rather than from the page, because a
    # sidebar section is narrow and its right column is nowhere near the page's.
    right_edge = max((row.x1 for row, _ in buffer), default=base)
    dated = [row for row, _ in buffer if _anchors_entry(row)]

    if not dated:
        entry = heading_lookup.identify((section.heading or "").strip())
        starts = _titled_without_dates(buffer, body, marked,
                                       entry["category"] if entry else None)
        if not starts:
            section.items = [row.text for row, _ in buffer]
            return
        for position, start in enumerate(starts):
            end = starts[position + 1] if position + 1 < len(starts) else len(buffer)
            title_rows = [start]
            while (title_rows[-1] + 1 < end
                   and title_rows[-1] + 1 not in
                   [i for i, (r, _) in enumerate(buffer)
                    if _starts_with_glyph(r.text) or _word_bullet(r.text)]
                   and _style_of(buffer[title_rows[-1] + 1][0], body)
                   == _style_of(buffer[start][0], body)):
                title_rows.append(title_rows[-1] + 1)
            title = "   ".join(buffer[i][0].text for i in title_rows)
            entry = Entry(title=title, dates="")
            for index in range(title_rows[-1] + 1, end):
                row = buffer[index][0]
                if _starts_with_glyph(row.text) or _word_bullet(row.text):
                    entry.bullets.append(_strip_glyph(row.text))
                    entry.content.append(("bullet", _strip_glyph(row.text)))
                elif _in_the_right_column(row, base, right_edge):
                    entry.asides.append(row.text)
                    entry.content.append(("aside", row.text))
                else:
                    entry.description.append(row.text)
                    entry.content.append(("line", row.text))
            section.entries.append(entry)
        if starts[0] > 0:
            section.items = [buffer[i][0].text for i in range(starts[0])]
        return

    current: Entry | None = None
    # An employer printed above the role it refers to:
    #
    #     Trust Square                      Zurich, Switzerland
    #     Werkstudent, directly reporting to the CEO
    #     Projektmanager                    Jul 2024 - Mar 2025
    #
    # That is one job, not three. The employer and anything between it and the
    # dated role are held here until the row below says which they belong to.
    held: list[layout.Row] = []

    def release() -> None:
        """The held rows were an entry in their own right after all."""
        nonlocal held, current
        if not held:
            return
        current = Entry(title=held[0].text,
                        description=[r.text for r in held[1:]],
                        content=[("line", r.text) for r in held[1:]])
        section.entries.append(current)
        held = []

    # The right-hand edge of this section's text, used to tell a wrapped line
    # from a new one. Rows that carry a right-aligned field (a date, a place)
    # reach further than the prose does, so they are left out of the measure.
    # Rows carrying a right-aligned field reach further than the prose does,
    # so they are left out. Too few prose rows and there is no measure to
    # speak of: one short line would otherwise set the margin at its own
    # width and make every line below it look like a continuation.
    prose = [row for row, _ in buffer if len(row.pieces) == 1]
    measure = max((row.x1 for row in prose), default=0.0) if len(prose) >= 3 else 0.0

    previous_text = ""
    previous_row: layout.Row | None = None
    # Where a CV prints no markers, a line is a bullet only if it is indented
    # beyond the TITLE of the entry it sits under - not merely beyond the
    # section's left margin. bad cv 9 puts its dates in a left column and
    # everything else in a right one, so every description line is indented
    # from the section margin; measuring against that turned a CV with no
    # bullets at all into one with twenty-four.
    title_indent = base
    for row, gap in buffer:
        here = row.indent
        subordinate = (here > title_indent + SUBORDINATE_INDENT
                       or _starts_with_glyph(row.text) or _word_bullet(row.text))
        # Where the CV marks its bullets, only a marked line is one. Where it
        # does not, a deeper indent is the only evidence there is.
        printed = _starts_with_glyph(row.text) or _word_bullet(row.text)
        bullet = printed or (not marked and here > title_indent + SUBORDINATE_INDENT)

        # A line wrapped from the one above belongs to it, whatever it looks
        # like on its own.
        # A line carrying its own marker always starts a new bullet. One that
        # is only indented might instead be the rest of the bullet above it -
        # "...to streamline content, saving several" / "hours of manual work
        # per month." is one bullet, and counting it as two inflated a CV
        # that prints no markers at all from 14 bullets to 27.
        same_level = (previous_row is not None
                      and abs(row.indent - previous_row.indent)
                      <= SUBORDINATE_INDENT)
        # A row that states its own dates begins an entry, whatever the line
        # above it did. Without this, two bare jobs listed one after the
        # other were read as a single job with a very long title.
        # A bold row is never the tail of a line that is not bold. bad cv 10
        # sets its entry titles bold and its description plain, and the line
        # above "Baccalaureat General   Graduated 2024" happened to reach the
        # margin - so a whole degree was swallowed as the remainder of the
        # sentence before it. "Graduated 2024" is not a date pattern, so
        # nothing else was going to rescue it.
        # Set bolder OR bigger than the line above it. On bad cv 10 the
        # degree line "Baccalaureat General   Graduated 2024" is 8pt over a
        # 7.5pt body while the line above it is 7.5pt, and its bold flag did
        # not survive the font name - so weight alone would not have saved it,
        # and a whole degree was swallowed as the remainder of the sentence
        # before it. "Graduated 2024" matches no date pattern, so nothing else
        # was going to rescue it either.
        starts_fresh = previous_row is not None and (
            (row.bold and not previous_row.bold)
            or row.size > previous_row.size + MEASURE_SLACK)
        wrapped = (not printed and same_level and not _anchors_entry(row)
                   and not starts_fresh
                   and (_continues(row.text, previous_text)
                        or _ran_to_the_margin(previous_row, measure)))
        if wrapped and (current is not None or held):
            if held:
                held[-1] = _joined(held[-1], row)
            elif current.bullets:
                current.bullets[-1] += " " + row.text
                _extend_last(current, "bullet", row.text)
            elif current.description:
                current.description[-1] += " " + row.text
                _extend_last(current, "line", row.text)
            else:
                current.title += " " + row.text
            previous_text = row.text
            previous_row = row
            continue
        previous_text = row.text
        previous_row = row

        if not subordinate and _anchors_entry(row):
            if held:
                current = Entry(title=f"{held[0].text}   {row.text}",
                                dates=_date_text(row.text),
                                description=[r.text for r in held[1:]],
                                content=[("line", r.text) for r in held[1:]])
                title_indent = min(_text_indent(held[0]), _text_indent(row))
                held = []
            else:
                current = Entry(title=row.text, dates=_date_text(row.text))
                title_indent = _text_indent(row)
            section.entries.append(current)
            continue

        # A bullet, or a wide gap, settles it: whatever is held was its own
        # entry and this row is not part of a job title.
        if bullet or gap >= BLOCK_GAP * body:
            release()
            if current is None:
                current = Entry(title=row.text)
                section.entries.append(current)
                continue
            if bullet:
                current.bullets.append(_strip_glyph(row.text))
                current.content.append(("bullet", _strip_glyph(row.text)))
            else:
                if _in_the_right_column(row, base, right_edge):
                    current.asides.append(row.text)
                    current.content.append(("aside", row.text))
                else:
                    current.description.append(row.text)
                    current.content.append(("line", row.text))
            continue

        # An un-dated row at the section's margin: either an employer whose
        # role follows, or a line of description. Hold it and let the next
        # row decide.
        if held or row.bold or current is None:
            held.append(row)
            continue
        # A right-column field, wherever it falls: the city under an entry
        # title, whether the CV prints the place above the date or below it.
        # Position decides, so the order and the language do not matter.
        if _in_the_right_column(row, base, right_edge):
            current.asides.append(row.text)
            current.content.append(("aside", row.text))
            continue
        current.description.append(row.text)
        current.content.append(("line", row.text))
    release()


def _text_indent(row: layout.Row) -> float:
    """
    Where this row's TEXT begins, ignoring a date printed to its left.

    "02/2026 - Heute    Universität St. Gallen" starts at the left margin,
    but only its date does; the entry itself begins where the right-hand
    column does, and that is what the lines beneath it are indented from.
    Measuring from the date put every description line far to the right of
    its own title and read all of them as bullets.
    """
    pieces = sorted(row.pieces, key=lambda p: p.x0)
    if len(pieces) > 1 and _is_only_a_date(pieces[0].text):
        return pieces[1].indent
    return row.indent


def _is_only_a_date(text: str) -> bool:
    """A field that holds a date and essentially nothing else."""
    stripped = text.strip()
    if not stripped or len(stripped) > 32:
        return False
    if SINGLE_DATE.match(stripped):
        return True
    match = DATE_RANGE.search(stripped)
    return bool(match) and len(match.group(0)) >= len(stripped) * 0.7


def _extend_last(entry: Entry, kind: str, text: str) -> None:
    """Add a wrapped line to the last thing of its kind, keeping the order."""
    for index in range(len(entry.content) - 1, -1, -1):
        if entry.content[index][0] == kind:
            entry.content[index] = (kind, entry.content[index][1] + " " + text)
            return
    entry.content.append((kind, text))


def _joined(first: layout.Row, second: layout.Row) -> layout.Row:
    """One row carrying the text of two, for a title wrapped over two lines."""
    return layout.Row(pieces=first.pieces + second.pieces)


def _date_text(text: str) -> str:
    match = DATE_RANGE.search(text)
    return match.group(0) if match else ""


def _strip_glyph(text: str) -> str:
    """The line without its bullet marker, whichever marker this CV uses.

    Also strips a marker this document TAUGHT us (_LEARNED): good cv 5 marks
    its bullets with ">", which is not in BULLET_GLYPHS, so the renderer was
    printing "- > Designed and implemented..." - two markers, one of them the
    student's. The model then read ">" as the start of a title and turned a
    bulleted list into seven entries with no detail.
    """
    stripped = text.lstrip()
    if stripped[:1] in BULLET_GLYPHS or stripped[:1] in _LEARNED:
        return stripped[1:].strip()
    if _word_bullet(stripped):
        return stripped[2:].strip()
    return stripped
