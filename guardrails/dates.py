"""
Date ranges on a CV, in whatever format the student wrote them.

This is the single date parser for the whole project. There used to be three
more - one in cv_facts.py, one in grading.py, one inline in pii.py - and they had
quietly drifted apart, so a CV written as "2019 - 2021" produced zero gap or
overlap findings while the same CV written as "Sep 2019 - Jun 2021" produced
several. Nobody would have noticed until a student was told their timeline was
clean when it was not.

Formats handled, because real CVs use all of them:

    Sep 2024 - Jun 2025        three-letter month, EN or DE
    September 2021 - April 2024   full month name
    Feb,2022-Nov,2022          LaTeX templates write it this way
    09/2024 - Present          numeric month, very common on Swiss CVs
    10.2021 - Heute            numeric month, German dot notation
    2019 - 2021                year only
    3un 2025 - Gun 2026        a scanned CV with OCR damage in the month

The parser produces a month index for arithmetic. Where a range gives only a
year, the start is treated as January and the end as December - the widest
reading, so an ordinary academic year is never reported as a gap.
"""

import re
from datetime import date

MONTHS = {
    "jan": 1, "january": 1, "januar": 1, "jän": 1,
    "feb": 2, "february": 2, "februar": 2,
    "mar": 3, "march": 3, "mär": 3, "maerz": 3, "märz": 3, "marz": 3, "mrz": 3,
    "apr": 4, "april": 4,
    "may": 5, "mai": 5,
    "jun": 6, "june": 6, "juni": 6,
    "jul": 7, "july": 7, "juli": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "okt": 10, "oktober": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12, "dez": 12, "dezember": 12,
}

PRESENT_WORDS = (r"present|current|currently|now|today|ongoing|date|"
                 r"heute|aktuell|laufend|jetzt|bis heute")

# One end of a range. Ordered most specific first so "September 2021" is not
# read as the bare year 2021 with stray text in front of it.
_ENDPOINT = (
    r"(?:"
    # The whitespace is capped deliberately. Allowing \s* let a column-aligned
    # CV line ("Matura              2013") read the preceding word as a month.
    r"[A-Za-zäöüÄÖÜ]{3,9}\.?,?[ \t]{0,2}(?:19|20)\d{2}"  # Sep 2024 / Feb,2022
    r"|[A-Za-z0-9]{3,4}\.?[ \t]{1,2}(?:19|20)\d{2}"      # 3un 2025 (OCR damage)
    r"|(?:0?[1-9]|1[0-2])\s*[./]\s*(?:19|20)\d{2}"       # 09/2024 / 10.2021
    r"|(?:19|20)\d{2}"                                    # 2019
    r")"
)
_SEPARATOR = r"\s*(?:[-–—]{1,2}|\bto\b|\bbis\b|\buntil\b)\s*"

RANGE_RE = re.compile(
    rf"(?P<start>{_ENDPOINT}){_SEPARATOR}(?P<end>{_ENDPOINT}|(?:{PRESENT_WORDS}))",
    re.IGNORECASE,
)

_MONTH_YEAR = re.compile(r"^([A-Za-z0-9äöüÄÖÜ]{3,9})\.?,?\s*((?:19|20)\d{2})$")
_NUMERIC = re.compile(r"^(\d{1,2})\s*[./]\s*((?:19|20)\d{2})$")
_YEAR_ONLY = re.compile(r"^((?:19|20)\d{2})$")

# A gap shorter than a semester is the shape of an ordinary academic year, not
# something to raise with a student. Career Services asked for a semester floor.
GAP_THRESHOLD_MONTHS = 6


def _month_index(year: int, month: int) -> int:
    return year * 12 + month


def parse_endpoint(token: str, *, is_end: bool) -> tuple[int, bool]:
    """
    One end of a range -> (month index, month_was_explicit).

    `is_end` decides what a bare year means: a range written "2019 - 2021"
    covers January 2019 to December 2021, so the two ends resolve differently.
    """
    token = token.strip()
    if re.fullmatch(PRESENT_WORDS, token, re.IGNORECASE):
        today = date.today()
        return _month_index(today.year, today.month), True

    match = _NUMERIC.match(token)
    if match:
        return _month_index(int(match.group(2)), int(match.group(1))), True

    match = _MONTH_YEAR.match(token)
    if match:
        name = match.group(1).strip(".").lower()
        year = int(match.group(2))
        if name in MONTHS:
            return _month_index(year, MONTHS[name]), True
        # An unrecognised word where a month belongs is OCR damage. Fall back to
        # the widest reading rather than dropping the entry entirely - a damaged
        # CV is exactly when the timeline check is most worth running.
        return _month_index(year, 12 if is_end else 1), False

    match = _YEAR_ONLY.match(token)
    if match:
        year = int(match.group(1))
        return _month_index(year, 12 if is_end else 1), False

    return 0, False


def extract_ranges(text: str) -> list[dict]:
    """Every date range in the text, sorted by start. Malformed ones are skipped."""
    ranges = []
    for match in RANGE_RE.finditer(text):
        start_idx, start_explicit = parse_endpoint(match.group("start"), is_end=False)
        end_idx, end_explicit = parse_endpoint(match.group("end"), is_end=True)
        if not start_idx or not end_idx or end_idx < start_idx:
            continue
        ranges.append({
            "raw": match.group(0).strip(),
            "start_idx": start_idx,
            "end_idx": end_idx,
            "months_explicit": start_explicit and end_explicit,
        })
    ranges.sort(key=lambda r: r["start_idx"])
    return ranges


FINDING_TEXT = {
    "en": {
        "overlap": "{first} and {second} run at the same time. If one was part-time or "
                   "alongside your studies, say so on the CV so a reader isn't left "
                   "working it out.",
        "gap": "There's a gap of about {months} months between {first} and {second}. You "
               "don't need to over-explain it — a short line about what you were doing is "
               "usually enough, and it's a good thing to talk through with your coach.",
    },
    "de": {
        "overlap": "{first} und {second} laufen zeitgleich. Wenn eines davon Teilzeit oder "
                   "neben dem Studium war, schreib das in den Lebenslauf, damit es sich "
                   "niemand zusammenreimen muss.",
        "gap": "Zwischen {first} und {second} liegt eine Lücke von rund {months} Monaten. "
               "Du musst das nicht ausführlich erklären — ein kurzer Satz dazu, was du in "
               "der Zeit gemacht hast, genügt meistens, und es lohnt sich, das mit deinem "
               "Coach zu besprechen.",
    },
}


def find_findings(text: str, labels: dict | None = None,
                  lang: str = "en") -> list[dict]:
    """
    Overlaps and gaps, written for the student to read, in `lang`.

    The old wording ("ask rather than assume", "ask before treating it as a
    weakness") was instruction addressed to the model and was being printed to
    students verbatim - both reviewers flagged it independently. It was also
    English-only, which is how it reached German reports untranslated.

    `labels` optionally maps a raw range to the entry it belongs to, so a finding
    can name the experiences rather than only the dates.

    Returns [{kind, first, second, months, text}].
    """
    labels = labels or {}
    phrases = FINDING_TEXT.get(lang, FINDING_TEXT["en"])
    ranges = extract_ranges(text)
    findings = []

    def name(raw: str) -> str:
        entry = labels.get(raw)
        return f"{entry} ({raw})" if entry else f'"{raw}"'

    for i in range(len(ranges) - 1):
        a, b = ranges[i], ranges[i + 1]
        # An overlap is only reported when both ranges state their months. With
        # years alone the boundaries are this parser's own guess (January and
        # December), so "2013 - 2017" against "2017 - 2018" would be reported as
        # concurrent when the student simply finished one and started the next.
        both_explicit = a["months_explicit"] and b["months_explicit"]
        if a["end_idx"] > b["start_idx"] and both_explicit:
            findings.append({
                "kind": "overlap", "first": a["raw"], "second": b["raw"], "months": None,
                "text": phrases["overlap"].format(first=name(a["raw"]),
                                                  second=name(b["raw"])),
            })
        gap = b["start_idx"] - a["end_idx"]
        if gap > GAP_THRESHOLD_MONTHS:
            findings.append({
                "kind": "gap", "first": a["raw"], "second": b["raw"], "months": gap,
                "text": phrases["gap"].format(first=name(a["raw"]),
                                              second=name(b["raw"]), months=gap),
            })

    return findings


def uses_year_only(text: str) -> list[str]:
    """
    Ranges written with years but no months. A reader cannot tell a three-month
    internship from a twelve-month one, and the gap check has to guess.
    """
    return [r["raw"] for r in extract_ranges(text) if not r["months_explicit"]]
