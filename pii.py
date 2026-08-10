"""
Best-effort PII stripping for extracted CV / job description text.

Scope, per the requirements doc: name, personal email, phone, address,
date of birth, nationality, marital status, photo.

Photo is handled implicitly: extraction only ever pulls text, so an
image never reaches this module or the model in the first place.

Everything else here is regex/keyword based. That is good enough for
a same-day prototype, not good enough to certify as compliant PII
stripping for real student data - see README for the honest version
of that statement.
"""

import re

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Loose international phone matcher: groups of digits separated by
# spaces/dashes/dots/parens, at least 7 digits total. Deliberately
# permissive - false positives (e.g. a course code) are an acceptable
# cost for a prototype, false negatives on real phone numbers are not.
PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s.\-]?)?(\(?\d{2,4}\)?[\s.\-]?){2,5}\d{2,4}"
)

DOB_KEYWORDS = re.compile(
    r"(date of birth|born on|born in|geburtsdatum|geboren am|geb\.)",
    re.IGNORECASE,
)
DATE_NEAR_RE = re.compile(
    r"(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{1,2}\s+"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)"
    r"[a-z]*\s+\d{4})",
    re.IGNORECASE,
)

NATIONALITY_RE = re.compile(
    r"^.*(nationality|staatsangehörigkeit|citizenship)\s*[:\-]?\s*.*$",
    re.IGNORECASE | re.MULTILINE,
)
MARITAL_RE = re.compile(
    r"^.*(marital status|familienstand)\s*[:\-]?\s*.*$",
    re.IGNORECASE | re.MULTILINE,
)
MARITAL_WORDS_RE = re.compile(
    r"\b(single|married|verheiratet|ledig|geschieden|divorced|widowed|verwitwet)\b",
    re.IGNORECASE,
)

SECTION_HEADERS = re.compile(
    r"^\s*(education|ausbildung|professional experience|berufserfahrung|"
    r"work experience|experience|skills|kenntnisse|languages|sprachen|"
    r"extracurricular|interests|profile|summary|projects)\b",
    re.IGNORECASE,
)


def _redact_name_header(text: str) -> tuple[str, bool]:
    """
    Best-effort heuristic: on a CV, the student's name is almost always
    the first non-empty line, before any recognized section header.
    This is a heuristic, not a name-entity recognizer - it will
    misfire on CVs with an unusual header (a tagline, a title block,
    etc). Flagged clearly in the return value so the caller can warn.
    """
    lines = text.splitlines()
    redacted_any = False
    out_lines = []
    header_seen = False
    for line in lines:
        if not header_seen and SECTION_HEADERS.match(line):
            header_seen = True
        if not header_seen and line.strip() and not header_seen:
            # First non-empty line(s) before any section header: treat
            # as name / header block only for the very first such line.
            if not redacted_any and len(line.strip()) < 60:
                out_lines.append("[NAME REDACTED]")
                redacted_any = True
                continue
        out_lines.append(line)
    return "\n".join(out_lines), redacted_any


def strip_pii(text: str) -> dict:
    """
    Returns {"text": redacted_text, "redactions": [labels applied]}.
    """
    redactions = []
    working = text

    if EMAIL_RE.search(working):
        working = EMAIL_RE.sub("[EMAIL REDACTED]", working)
        redactions.append("email")

    # DOB must run BEFORE the phone regex - a date like 14.03.2001 is
    # otherwise indistinguishable from a phone number to PHONE_RE, and
    # phone would consume it first if it ran first.
    if DOB_KEYWORDS.search(working):
        lines = working.splitlines()
        new_lines = []
        for line in lines:
            if DOB_KEYWORDS.search(line):
                line = DATE_NEAR_RE.sub("[DOB REDACTED]", line)
            new_lines.append(line)
        working = "\n".join(new_lines)
        redactions.append("date_of_birth")

    if PHONE_RE.search(working):
        # Avoid nuking short numeric tokens like years or GPA figures:
        # only redact matches with at least 7 digits.
        def _phone_sub(m):
            digits = re.sub(r"\D", "", m.group(0))
            return "[PHONE REDACTED]" if len(digits) >= 7 else m.group(0)

        new_working = PHONE_RE.sub(_phone_sub, working)
        if new_working != working:
            redactions.append("phone")
        working = new_working

    if NATIONALITY_RE.search(working):
        working = NATIONALITY_RE.sub("[NATIONALITY REDACTED]", working)
        redactions.append("nationality")

    if MARITAL_RE.search(working):
        working = MARITAL_RE.sub("[MARITAL STATUS REDACTED]", working)
        redactions.append("marital_status")
    elif MARITAL_WORDS_RE.search(working):
        working = MARITAL_WORDS_RE.sub("[MARITAL STATUS REDACTED]", working)
        redactions.append("marital_status")

    working, name_redacted = _redact_name_header(working)
    if name_redacted:
        redactions.append("name (best-effort heuristic)")

    return {"text": working, "redactions": redactions}
