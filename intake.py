"""
How a CV gets from an uploaded file to the text the model reads.

Two readers, each doing the half it is good at:

  extraction.py  the file's own facts - page count, embedded images, tables.
                 Those live in the container and no amount of text analysis
                 recovers them.
  structure/     the text itself, read in the order a person reads the page.

The second one is the point. A flat extraction walks a PDF row by row, so a
two-column CV arrives with its columns welded together:

    Russisch (Al) BERUFSERFAHRUNG
    Excel • MS Office Freelance - Zürich 01.2026 - heute
    Chutzenstrasse 68, 3007 JUNIOR LEAD BUYER WANDER AG

The first line is a language level from a sidebar glued to the Work Experience
heading. The third is a street address glued to a job title - and the address
pattern matched the whole of it, so the job title was redacted along with the
address, losing exactly what the job-description alignment is built on.

Reading the columns in order fixes all of that before redaction ever runs,
which is why the order here is file -> tree -> render -> redact, and why the
redaction layer itself needs no changes: by the time it sees the text, there
are no welded lines left in it.

The tree is not trusted blindly. If it comes back with materially less text
than the flat reader found, the flat text is used instead and the fact is
recorded: a parser that silently drops half a CV is worse than a parser that
welds two columns, because the student is never told.
"""

from __future__ import annotations

from extraction import ExtractionResult, extract_text
from guardrails import headings as heading_lookup

# Below this share of the flat reader's words, the tree is not believed.
# Deliberately generous: the tree drops nothing on any of the 25 samples, so
# anything near this line means something has gone wrong, not that a CV is
# unusual.
KEEP_SHARE = 0.9


def _words(text: str) -> int:
    return len(text.split())


def _entries_by_heading(document) -> dict:
    """
    The tree's entries, keyed by heading, in the shape cv_facts counts.

    This is the handover. Without it the tree's work reaches the report only
    as better TEXT, and cv_facts re-derives the entries from that text with a
    date pattern - which is how good cv 6 ended up with 8 entries when the
    tree had found the correct 9, and how a CV with its dates in a left-hand
    column ends up with entries named "2019-2023".

    Sub-headings are walked too, and a parent's own entries are kept: a
    heading that groups sub-headings can still carry entries of its own, and
    dropping them is the bug that made exp cv bad 1 look like it had none.
    """
    out: dict = {}

    def shape(entry, offset: int) -> dict:
        return {
            "line": entry.title,
            "title_line": entry.title,
            "offset": offset,
            "bullets": list(entry.bullets),
            "description": list(entry.description),
            # The tree knows where an entry ends, so nothing is "stacked" in
            # the sense the text parser means - that flag exists to undo a
            # guess this layer does not have to make.
            "stacked_with_next": False,
        }

    def descendants(section):
        """Every entry at or below this heading, in document order."""
        yield from section.entries
        for child in section.subsections:
            yield from descendants(child)

    def walk(section) -> None:
        if section.heading:
            key = heading_lookup.normalise(section.heading)
            # A heading with no entries of its own but sub-headings beneath it
            # means "everything under me": on exp cv bad 1 the seven jobs sit
            # under an employer sub-heading inside BERUFLICHE ERFAHRUNG, and
            # keying that heading to its own (empty) list reported a work
            # section with nothing in it. Where the heading DOES carry its own
            # entries they are used as they are, so nothing is counted twice.
            source = (section.entries if section.entries
                      else list(descendants(section)))
            rows = [shape(e, i) for i, e in enumerate(source)]
            # A heading that appears twice keeps both sets, in document order.
            out.setdefault(key, []).extend(rows)
        for child in section.subsections:
            walk(child)

    for section in document.sections:
        walk(section)
    # A section the tree read as a list - languages, skills, interests - has no
    # entries, and must say so rather than fall back to the pattern parser,
    # which would read "German: native" as an activity with no description.
    return out


def read_cv(file_bytes: bytes, filename: str) -> ExtractionResult:
    """
    The CV as text, in reading order, with the file's own facts attached.

    Same contract as extract_text: never raises, and `ok` is False only when
    the document could not be read at all.
    """
    flat = extract_text(file_bytes, filename)
    if not flat.ok:
        return flat

    meta = dict(flat.meta or {})
    meta.setdefault("reader", "flat")
    try:
        from structure import read as structure_read, to_text
        document = structure_read.read(file_bytes, filename)
        rendered = to_text.render(document)
    except Exception as error:                                   # noqa: BLE001
        meta["reader_note"] = f"column-aware reader unavailable: {error}"
        return ExtractionResult(True, flat.text, meta=meta)

    if _words(rendered) < _words(flat.text) * KEEP_SHARE:
        meta["reader_note"] = (
            f"column-aware reader returned {_words(rendered)} words against "
            f"{_words(flat.text)} from the flat reader, so the flat text was used")
        return ExtractionResult(True, flat.text, meta=meta)

    meta["reader"] = "tree"
    # What the tree could not make sense of. A section it cannot read is a
    # section the student must be told about rather than one that disappears.
    meta["reader_confident"] = document.confident
    meta["reader_notes"] = list(document.notes or [])
    meta["char_count"] = len(rendered.strip())
    # The structure itself, for cv_facts to count rather than re-derive.
    meta["parsed_entries"] = _entries_by_heading(document)
    return ExtractionResult(True, rendered, meta=meta)
