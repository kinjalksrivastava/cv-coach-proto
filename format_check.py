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
    "arial", "helvetica", "helveticaneue", "times", "timesnewroman", "timesnewromanps",
    "calibri", "cambria", "georgia", "garamond", "verdana", "tahoma", "trebuchet",
    "trebuchetms", "bookantiqua", "palatino", "palatinolinotype", "segoeui",
    "liberationsans", "liberationserif", "nimbusroman", "nimbussans", "dejavusans",
    "couriernew", "lato", "opensans", "roboto", "sourcesanspro",
}

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
}

# Bullet marks that are safe. Anything else at the start of a list line - an
# emoji, an icon glyph, a private-use character from an icon font - is the kind
# of thing that turns into mojibake or vanishes in an ATS parse.
SAFE_BULLETS = set("-–—*•·◦o")
BULLET_LINE_RE = re.compile(r"^\s*([^\s\w])\s+\S")

# Roughly one page of a text-only CV. Used only where a real page count is
# unavailable (DOCX, pasted text), and labelled as an estimate wherever shown.
CHARS_PER_PAGE_ESTIMATE = 2800

DENSE_CHARS_PER_PAGE = 4200
SPARSE_CHARS_PER_PAGE = 900


def _heading_candidates(text: str) -> list[str]:
    """Short standalone lines that read as headings — all-caps or title case."""
    found = []
    for line in text.splitlines():
        stripped = line.strip().strip(":").strip()
        if not (2 < len(stripped) <= 45):
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


def nonstandard_fonts(meta: dict) -> list[str]:
    return [
        font for font in meta.get("fonts", [])
        if font.lower().replace(" ", "").replace("_", "") not in STANDARD_FONTS
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


def _density_row(meta: dict, char_count: int) -> dict:
    pages = meta.get("page_count")
    if not pages:
        return {"check": "Text density", "status": UNKNOWN,
                "comment": "Not assessable — only the extracted text is available for "
                           "this file type, not the page layout."}
    per_page = char_count / pages
    if per_page > DENSE_CHARS_PER_PAGE:
        status, comment = ATTENTION, (
            f"About {per_page:,.0f} characters per page — dense. That usually means "
            "little breathing room between entries."
        )
    elif per_page < SPARSE_CHARS_PER_PAGE:
        status, comment = ATTENTION, (
            f"About {per_page:,.0f} characters per page — sparse. There may be room to "
            "say more about what you did."
        )
    else:
        status, comment = GOOD, (
            f"About {per_page:,.0f} characters per page — a readable amount of text per page."
        )
    return {"check": "Text density", "status": status,
            "comment": comment + " (Measured from the text; actual whitespace and "
                                 "spacing aren't visible to this tool.)"}


def _ats_row(meta: dict, text: str) -> dict:
    problems, notes = [], []

    fonts = nonstandard_fonts(meta)
    if fonts:
        problems.append(f"non-standard font{'s' if len(fonts) > 1 else ''} "
                        f"({', '.join(fonts[:3])})")
    elif meta.get("fonts"):
        notes.append("standard fonts")

    headings = unconventional_headings(text)
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

    if meta.get("image_count"):
        problems.append(f"{meta['image_count']} embedded image(s) — text inside an image "
                        "is invisible to a parser")

    if not problems:
        comment = ("No parsing risks detected"
                   + (f" — {', '.join(notes)}." if notes else "."))
        return {"check": "Estimated ATS compatibility", "status": GOOD, "comment": comment}

    lead = f"{', '.join(notes).capitalize()}, but " if notes else "Detected: "
    return {"check": "Estimated ATS compatibility", "status": ATTENTION,
            "comment": lead + "; ".join(problems) + "."}


def run(text: str, meta: dict) -> list[dict]:
    """Returns the format-check rows: [{check, status, comment}]."""
    char_count = meta.get("char_count") or len(text.strip())
    return [_page_row(meta, char_count), _density_row(meta, char_count), _ats_row(meta, text)]


CRITERIA_NOTE = (
    "ATS compatibility is estimated from four things this tool can actually observe: "
    "standard fonts, conventional section headings, ordinary bullet characters, and no "
    "table- or image-based layout. It is an indication, not a guarantee — every "
    "applicant tracking system parses differently."
)
