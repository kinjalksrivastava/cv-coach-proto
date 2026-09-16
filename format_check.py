"""
The "CV Format Check" rows of the feedback report.

Built from facts, not from a model's impression. Page count, fonts, embedded
images and table-based layout come from extraction.py's `meta` (the file itself);
heading conventionality and bullet glyphs come from the text. A model reading
extracted text cannot see any of this, so asking it would produce a confident
guess - which is precisely what this report must not contain.

The honest limit, stated in the comment text the student actually reads: the
"layout" row measures TEXT DENSITY, not visual whitespace. Only extracted text
is available, so real whitespace is not observable. Density is a genuine proxy
for "overcrowded" and is labelled as such rather than dressed up as a layout
judgement.
"""

import re

GOOD, ATTENTION, UNKNOWN = "good", "attention", "unknown"

# Fonts that PDF/ATS parsers handle without complaint. Compared case- and
# space-insensitively against whatever the file actually embeds.
STANDARD_FONTS = {
    "arial", "helvetica", "helveticaneue", "times", "timesnewroman",
    "calibri", "cambria", "georgia", "garamond", "ebgaramond", "verdana", "tahoma",
    "trebuchet", "trebuchetms", "bookantiqua", "palatino", "palatinolinotype",
    "segoeui", "liberationsans", "liberationserif", "nimbusroman", "nimbussans",
    "dejavusans", "couriernew", "courierprime", "lato", "opensans", "roboto",
    "sourcesanspro", "sourcecodepro", "montserrat", "opensauce", "inter",
}

# PostScript names carry suffixes that have nothing to do with the typeface:
# "TimesNewRomanPSMT" and "ArialMT" are Times New Roman and Arial. Not stripping
# these is why a perfectly ordinary CV was told its fonts were non-standard.
FONT_SUFFIXES = ("psmt", "ps", "mt", "std", "pro", "lt")

# Headings an ATS parser is likely to recognise, EN + DE.
CONVENTIONAL_HEADINGS = {
    "work experience", "professional experience", "experience", "employment",
    "employment history", "berufserfahrung", "praktische erfahrung", "praktika",
    "education", "ausbildung", "studium",
    "skills", "technical skills", "it skills", "kenntnisse", "fähigkeiten", "edv",
    "languages", "sprachen", "language skills",
    "extracurricular activities", "extracurricular", "ausserschulische aktivitäten",
    "außerschulische aktivitäten", "engagement",
    "interests", "hobbies", "interessen", "freizeit",
    "certificates", "certifications", "courses and certificates", "zertifikate",
    "weiterbildung", "kurse",
    "publications", "publikationen", "research", "forschung",
    "projects", "projekte",
    "awards", "honours", "honors", "auszeichnungen", "stipendien", "scholarships",
    "references", "referenzen",
    "profile", "summary", "profil", "kurzprofil",
    "volunteering", "ehrenamt", "freiwilligenarbeit",
    "it", "tools", "training", "military service", "militärdienst", "zivildienst",
    "personal details", "contact", "kontakt",
    # Career Services confirmed these read as normal CV headings and should not
    # be reported as parsing risks.
    "additional information", "community experience", "core competences",
    "core competencies", "hobbies and interests", "interests and hobbies",
    "languages and it skills", "work history", "voluntary work",
}

# Bullet marks that are safe. Anything else at the start of a list line - an
# emoji, an icon glyph, a private-use character from an icon font - is the kind
# of thing that turns into mojibake or vanishes in an ATS parse.
SAFE_BULLETS = set("-–—*•·◦o")
BULLET_LINE_RE = re.compile(r"^\s*([^\s\w])\s+\S")

# Roughly one page of a text-only CV. Used only where a real page count is
# unavailable (DOCX, pasted text), and labelled as an estimate wherever shown.
CHARS_PER_PAGE_ESTIMATE = 2800


def _heading_candidates(text: str) -> list[str]:
    """Short standalone lines that read as headings — all-caps or title case."""
    found = []
    for line in text.splitlines():
        stripped = line.strip().strip(":").strip()
        if not (2 < len(stripped) <= 45):
            continue
        # A bullet is never a heading. Without this, "• Website Development" was
        # reported to the student as an unrecognisable section header.
        if stripped[0] in "-–—•·*▪◦‣":
            continue
        # "German: Native" is a data line, not a section heading. Reporting it as
        # an unrecognisable header was another manufactured finding.
        if re.match(r"^[^:]{2,30}:\s*\S", stripped):
            continue
        letters = [c for c in stripped if c.isalpha()]
        if len(letters) < 3:
            continue
        if any(ch.isdigit() for ch in stripped) or "@" in stripped or "[" in stripped:
            continue
        # A heading is either all-caps, or short title case. The comma test
        # keeps content lines out: "Reading, Sports, Travelling" is title case
        # and short, but it is an interests list, not a section heading.
        if "," in stripped:
            continue
        if all(c.isupper() for c in letters) or (stripped.istitle() and len(stripped.split()) <= 4):
            found.append(stripped)
    return found


# Qualifiers that don't make a heading unconventional on their own.
HEADING_QUALIFIERS = ("selected", "relevant", "key", "further", "additional", "other",
                      "weitere", "ausgewählte", "sonstige")


def _is_conventional(heading: str) -> bool:
    """
    "Selected Publications", "Certifications & Training" and "IT & Languages" are
    all conventional; splitting on the connectives and dropping the qualifier is
    what stops the check from flagging ordinary headings as parsing risks.
    """
    value = heading.lower().strip(" :&/")
    if value in CONVENTIONAL_HEADINGS:
        return True
    words = value.split()
    while words and words[0] in HEADING_QUALIFIERS:
        words = words[1:]
    value = " ".join(words)
    if value in CONVENTIONAL_HEADINGS:
        return True
    parts = [p.strip() for p in re.split(r"\s*(?:&|/|\band\b|\bund\b|,)\s*", value) if p.strip()]
    return len(parts) > 1 and all(p in CONVENTIONAL_HEADINGS for p in parts)


def unconventional_headings(text: str) -> list[str]:
    return [h for h in _heading_candidates(text) if not _is_conventional(h)]


def unusual_bullets(text: str) -> list[str]:
    marks = set()
    for line in text.splitlines():
        match = BULLET_LINE_RE.match(line)
        if match and match.group(1) not in SAFE_BULLETS:
            marks.add(match.group(1))
    return sorted(marks)


def _normalise_font(name: str) -> str:
    value = re.sub(r"[^a-z]", "", name.lower())
    changed = True
    while changed:
        changed = False
        for suffix in FONT_SUFFIXES:
            if value.endswith(suffix) and len(value) > len(suffix) + 3:
                value, changed = value[: -len(suffix)], True
                break
    return value


def nonstandard_fonts(meta: dict) -> list[str]:
    return [
        font for font in meta.get("fonts", [])
        if _normalise_font(font) not in STANDARD_FONTS
    ]


def _page_row(meta: dict, char_count: int) -> dict:
    pages = meta.get("page_count")
    if pages:
        if pages <= 2:
            return {"check": "Length", "status": GOOD,
                    "comment": f"{pages} page{'s' if pages > 1 else ''} — appropriate "
                               "for a student or early-career CV."}
        return {"check": "Length", "status": ATTENTION,
                "comment": f"{pages} pages. One page (two at most) is the expectation for "
                           "a student CV in the Swiss market — worth asking which content "
                           "is earning its space."}
    estimate = max(1, round(char_count / CHARS_PER_PAGE_ESTIMATE))
    return {"check": "Length", "status": GOOD if estimate <= 2 else ATTENTION,
            "comment": f"Roughly {estimate} page{'s' if estimate > 1 else ''} of text "
                       "(estimated from the text — the real page count isn't recoverable "
                       "from this file type)."}


# The text-density row was removed after review: it flagged a perfectly
# well-spaced CV as "dense" on a character count, and since only extracted text
# is available, real whitespace was never observable. A measurement that cannot
# see the thing it claims to judge does not belong in the report.


def _ats_row(meta: dict, text: str, facts: dict | None = None) -> dict:
    # Use the headings the parser actually identified rather than guessing them
    # out of the text. The heuristic version kept nominating content lines -
    # "• Website Development", "German: Native", "Chess" - as section headers a
    # parser might not recognise, which is nonsense the student has to wade past.
    if facts and facts.get("sections"):
        heading_source = [s["heading"] for s in facts["sections"]]
    else:
        heading_source = _heading_candidates(text)
    problems, notes = [], []

    fonts = nonstandard_fonts(meta)
    if fonts:
        problems.append(f"non-standard font{'s' if len(fonts) > 1 else ''} "
                        f"({', '.join(fonts[:3])})")
    elif meta.get("fonts"):
        notes.append("standard fonts")

    headings = [h for h in heading_source if not _is_conventional(h)]
    if headings:
        problems.append(
            "section headers some parsers may not recognise "
            f"({', '.join(headings[:3])}) — conventional wording such as "
            '"Work Experience" or "Education" parses more reliably'
        )
    else:
        notes.append("conventional section headers")

    bullets = unusual_bullets(text)
    if bullets:
        problems.append(f"unusual bullet or icon characters ({' '.join(bullets[:4])})")

    if meta.get("table_count"):
        problems.append(f"{meta['table_count']} table(s) — tables used for layout are a "
                        "common cause of scrambled ATS parsing")

    # One image on a CV in this market is almost always the portrait photo, which
    # is conventional here and carries no text. Only a cluster of images suggests
    # content has been baked into graphics where a parser cannot reach it.
    if meta.get("image_count", 0) > 1:
        problems.append(f"{meta['image_count']} embedded images — any text inside them "
                        "is invisible to a parser")

    if not problems:
        comment = ("No parsing risks detected"
                   + (f" — {', '.join(notes)}." if notes else "."))
        return {"check": "Estimated ATS compatibility", "status": GOOD, "comment": comment}

    lead = f"{', '.join(notes).capitalize()}, but " if notes else "Detected: "
    return {"check": "Estimated ATS compatibility", "status": ATTENTION,
            "comment": lead + "; ".join(problems) + "."}


def _writing_row(facts: dict) -> dict:
    """
    Typos, mis-scanned dates and mixed British/American spelling. Career Services
    asked for this in the format check after a CV went through with "Educatiqn"
    as a heading and "Gun 2026" as a date, neither of which was mentioned.
    """
    problems = []
    if facts.get("heading_typos"):
        problems.extend(facts["heading_typos"])
    if facts.get("month_typos"):
        problems.extend(facts["month_typos"])
    # Both halves are always reported, even the clean one. Listing only the
    # failures meant a CV with typos never learned its British/American spelling
    # had been checked at all.
    spelling_note = ("British and American spellings are both used ("
                     + ", ".join(facts["mixed_spelling"]) + ") - pick one and keep it "
                     "consistent") if facts.get("mixed_spelling") else \
                    "British/American spelling is used consistently"
    typo_note = "; ".join(problems) if problems else \
                "no obvious typos in headings or dates"
    status = ATTENTION if (problems or facts.get("mixed_spelling")) else GOOD
    return {"check": "Spelling and consistency", "status": status,
            "comment": f"Typos: {typo_note}. Spelling: {spelling_note}."}


def run(text: str, meta: dict, facts: dict | None = None) -> list[dict]:
    """Returns the format-check rows: [{check, status, comment}]."""
    char_count = meta.get("char_count") or len(text.strip())
    rows = [_page_row(meta, char_count), _ats_row(meta, text, facts)]
    if facts:
        rows.append(_writing_row(facts))
    return rows


CRITERIA_NOTE = (
    "An Applicant Tracking System (ATS) is software employers use to collect, scan and "
    "process applications digitally — many CVs are read by one before a person sees them. "
    "ATS compatibility is estimated from four things this tool can actually observe: "
    "standard fonts, conventional section headings, ordinary bullet characters, and no "
    "table- or image-based layout. It is an indication, not a guarantee — every "
    "applicant tracking system parses differently."
)
