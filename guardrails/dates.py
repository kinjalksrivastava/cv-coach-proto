"""
Best-effort date range extraction from CV text, to surface possible
gaps or overlaps for the bot to ASK about - never to assert as an
error itself. Per the requirements doc's edge case: an overlap could
be a genuine part-time/concurrent situation, and a gap is not
automatically a weakness. This module only produces flags; the system
prompt is responsible for turning a flag into a question, not a verdict.

Regex-based date parsing is inherently approximate (see README for the
honest version of that statement) - it's good enough to prompt the
right question, not to be trusted as ground truth.
"""

import re
from datetime import date

MONTHS = {
    "jan": 1, "january": 1, "januar": 1,
    "feb": 2, "february": 2, "februar": 2,
    "mar": 3, "march": 3, "mär": 3, "maerz": 3, "märz": 3, "marz": 3,
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

PRESENT_WORDS = "present|current|now|heute|aktuell|ongoing|laufend|today"

# The optional comma matters more than it looks: LaTeX CV templates routinely
# render dates as "Feb,2022-Nov,2022", and without it every range on such a CV
# is invisible to the gap/overlap check.
RANGE_RE = re.compile(
    r"(?P<smonth>[A-Za-zäöüÄÖÜ]{3,9})?\.?,?\s*(?P<syear>(?:19|20)\d{2})"
    r"\s*[-–—]\s*"
    r"(?:(?P<emonth>[A-Za-zäöüÄÖÜ]{3,9})\.?,?\s*(?P<eyear>(?:19|20)\d{2})"
    rf"|(?P<epresent>{PRESENT_WORDS}))",
    re.IGNORECASE,
)

# A gap shorter than a semester is not worth raising with a student - it is the
# shape of an ordinary academic year. Career Services asked for a semester as the
# floor; the prioritisation list says anything over six months unexplained.
GAP_THRESHOLD_MONTHS = 6


def _month_num(name: str | None) -> int:
    if not name:
        return 1  # no month given - assume the earliest month as a conservative bound
    return MONTHS.get(name.strip(".").lower(), 1)


def _month_idx(year: int, month: int) -> int:
    return year * 12 + month


def extract_ranges(text: str) -> list[dict]:
    """Returns a list of {raw, start_idx, end_idx} sorted by start."""
    today = date.today()
    present_idx = _month_idx(today.year, today.month)

    ranges = []
    for m in RANGE_RE.finditer(text):
        # The month groups match any 3-9 letter word, so "Club 2023 - present"
        # would otherwise be reported to the student as "Club 2023 - present".
        # An unrecognised word isn't a month: trim it out of the quoted range.
        raw = m.group(0).strip()
        if m.group("smonth") and m.group("smonth").strip(".").lower() not in MONTHS:
            raw = raw[raw.index(m.group("syear")):]

        syear = int(m.group("syear"))
        smonth = _month_num(m.group("smonth"))
        start_idx = _month_idx(syear, smonth)

        if m.group("epresent"):
            end_idx = present_idx
        else:
            eyear = int(m.group("eyear"))
            emonth = _month_num(m.group("emonth")) if m.group("emonth") else 12
            end_idx = _month_idx(eyear, emonth)

        if end_idx < start_idx:
            continue  # malformed match, skip rather than guess

        ranges.append({"raw": raw, "start_idx": start_idx, "end_idx": end_idx})

    ranges.sort(key=lambda r: r["start_idx"])
    return ranges


def find_findings(text: str, labels: dict | None = None) -> list[dict]:
    """
    Overlaps and gaps, written for the student to read.

    The old wording ("ask rather than assume", "ask before treating it as a
    weakness") was instruction addressed to the model, and it was being printed
    to students verbatim - both reviewers flagged it independently. Those are
    prompt concerns and do not belong in text a student sees.

    `labels` optionally maps a raw date range to the entry it belongs to, so the
    finding can name the experiences rather than just the dates.

    Returns [{kind, first, second, months, text}].
    """
    labels = labels or {}
    ranges = extract_ranges(text)
    findings = []

    def name(raw: str) -> str:
        entry = labels.get(raw)
        return f'{entry} ({raw})' if entry else f'"{raw}"'

    for i in range(len(ranges) - 1):
        a, b = ranges[i], ranges[i + 1]
        if a["end_idx"] > b["start_idx"]:
            findings.append({
                "kind": "overlap", "first": a["raw"], "second": b["raw"], "months": None,
                "text": (
                    f"{name(a['raw'])} and {name(b['raw'])} run at the same time. "
                    "If one was part-time or alongside your studies, say so on the CV so "
                    "a reader isn't left working it out."
                ),
            })
        gap = b["start_idx"] - a["end_idx"]
        if gap > GAP_THRESHOLD_MONTHS:
            findings.append({
                "kind": "gap", "first": a["raw"], "second": b["raw"], "months": gap,
                "text": (
                    f"There's a gap of about {gap} months between {name(a['raw'])} and "
                    f"{name(b['raw'])}. You don't need to over-explain it \u2014 a short line "
                    "about what you were doing is usually enough, and it's a good thing to "
                    "talk through with your coach."
                ),
            })

    return findings
