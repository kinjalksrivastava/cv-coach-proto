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

from guardrails import headings as heading_lookup

GOOD, ATTENTION, UNKNOWN = "good", "attention", "unknown"

# --- Every sentence a student reads from this module, in both languages -------
#
# These rows are built in code, so they used to be hard-coded English and were
# printed verbatim into a German report. Both reviewers reported it independently
# ("This section always seems to come in English, even when I selected German
# feedback"; "The report is mixing english and german feedback in the same
# report"). Nothing here may be left untranslated.

TEXT = {
    "en": {
        "length": "Length",
        "ats": "Estimated ATS compatibility",
        "writing": "Spelling and consistency",
        "pages_ok": "{n} page{s} — appropriate for a student or early-career CV.",
        "pages_many": "{n} pages. One page (two at most) is the expectation for a student "
                      "CV in the Swiss market — worth asking which content is earning "
                      "its space.",
        "pages_estimate": "Roughly {n} page{s} of text (estimated from the text — the real "
                          "page count isn't recoverable from this file type).",
        "fonts": "non-standard font{s} ({items})",
        "std_fonts": "standard fonts",
        "headings": "section headers some parsers may not recognise ({items}) — "
                    "conventional wording such as \"Work Experience\" or \"Education\" "
                    "parses more reliably",
        "std_headings": "conventional section headers",
        "bullets": "unusual bullet or icon characters ({items})",
        "icon_headings": "icon or symbol characters beside your section headings that "
                         "didn't survive the text extraction ({items}) — the headings "
                         "themselves are correct, but an ATS reads the file the same way "
                         "this tool did, so it's worth removing the icons",
        "tables": "{n} table(s) — tables used for layout are a common cause of scrambled "
                  "ATS parsing",
        "images": "{n} embedded images — any text inside them is invisible to a parser",
        "no_risks": "No parsing risks detected",
        "no_risks_with": "No parsing risks detected — {notes}.",
        "lead_but": "{notes}, but ",
        "lead_detected": "Detected: ",
        "spelling_mixed": "British and American spellings are both used ({items}) — pick "
                          "one and keep it consistent",
        "spelling_ok": "British/American spelling is used consistently",
        # Career Services' point: on the CV that produced "Educatiqn" the student
        # had written Education correctly and the extractor mangled it. Asserting
        # a typo blames them for the parse. The wording now states what came
        # through and leaves the cause open, which is also more useful: either it
        # is a typo worth fixing, or the file does not extract cleanly, and an
        # ATS will read it exactly the same way.
        "typo_heading": ('"{written}" came through where "{correct}" was expected. '
                         'If that is how it is written, it is a quick fix; if not, '
                         'the file is not extracting cleanly, which an ATS would '
                         'also struggle with'),
        "typo_month": '"{written}" came through where "{correct}" was expected',
        "typos_none": "no obvious typos in headings or dates",
        "writing_comment": "Typos: {typos}. Spelling: {spelling}.",
        "criteria": (
            "An Applicant Tracking System (ATS) is software employers use to collect, scan "
            "and process applications digitally — many CVs are read by one before a person "
            "sees them. ATS compatibility is estimated from four things this tool can "
            "actually observe: standard fonts, conventional section headings, ordinary "
            "bullet characters, and no table- or image-based layout. It is an indication, "
            "not a guarantee — every applicant tracking system parses differently."
        ),
    },
    "de": {
        "length": "Länge",
        "ats": "Geschätzte ATS-Kompatibilität",
        "writing": "Rechtschreibung und Konsistenz",
        "pages_ok": "{n} Seite{s} — passend für einen Lebenslauf zu Studienzeiten oder am "
                    "Berufseinstieg.",
        "pages_many": "{n} Seiten. Für einen studentischen Lebenslauf wird im Schweizer "
                      "Markt eine Seite erwartet, höchstens zwei — es lohnt sich zu "
                      "fragen, welche Inhalte ihren Platz wirklich verdienen.",
        "pages_estimate": "Rund {n} Seite{s} Text (aus dem Text geschätzt — die "
                          "tatsächliche Seitenzahl lässt sich aus diesem Dateiformat "
                          "nicht auslesen).",
        "fonts": "ungewöhnliche Schriftart{s} ({items})",
        "std_fonts": "gängige Schriftarten",
        "headings": "Abschnittstitel, die manche Parser nicht erkennen ({items}) — "
                    "gängige Bezeichnungen wie \"Berufserfahrung\" oder \"Ausbildung\" "
                    "werden zuverlässiger gelesen",
        "std_headings": "gängige Abschnittstitel",
        "bullets": "ungewöhnliche Aufzählungs- oder Icon-Zeichen ({items})",
        "icon_headings": "Icon- oder Symbolzeichen neben deinen Abschnittstiteln, die die "
                         "Textextraktion nicht überstanden haben ({items}) — die Titel "
                         "selbst sind korrekt, aber ein ATS liest die Datei genauso wie "
                         "dieses Tool, deshalb lohnt es sich, die Icons zu entfernen",
        "tables": "{n} Tabelle(n) — für das Layout genutzte Tabellen sind eine häufige "
                  "Ursache für fehlerhaftes ATS-Parsing",
        "images": "{n} eingebettete Bilder — Text darin ist für einen Parser unsichtbar",
        "no_risks": "Keine Parsing-Risiken erkannt",
        "no_risks_with": "Keine Parsing-Risiken erkannt — {notes}.",
        "lead_but": "{notes}, aber ",
        "lead_detected": "Erkannt: ",
        "spelling_mixed": "Britische und amerikanische Schreibweisen kommen beide vor "
                          "({items}) — entscheide dich für eine und bleib dabei",
        "spelling_ok": "Britische/amerikanische Schreibweise wird einheitlich verwendet",
        "typo_heading": ('"{written}" kam an, wo "{correct}" erwartet wurde. Wenn es '
                         'so geschrieben ist, ist das schnell korrigiert; wenn nicht, '
                         'lässt sich die Datei nicht sauber auslesen, womit auch ein '
                         'ATS Mühe hätte'),
        "typo_month": '"{written}" kam an, wo "{correct}" erwartet wurde',
        "typos_none": "keine offensichtlichen Tippfehler in Titeln oder Daten",
        "writing_comment": "Tippfehler: {typos}. Schreibweise: {spelling}.",
        "criteria": (
            "Ein Applicant Tracking System (ATS) ist Software, mit der Arbeitgeber "
            "Bewerbungen digital sammeln, scannen und verarbeiten — viele Lebensläufe "
            "werden davon gelesen, bevor ein Mensch sie sieht. Die ATS-Kompatibilität "
            "wird aus vier Dingen geschätzt, die dieses Tool tatsächlich beobachten kann: "
            "gängige Schriftarten, gängige Abschnittstitel, übliche Aufzählungszeichen "
            "und kein auf Tabellen oder Bildern aufgebautes Layout. Das ist ein Hinweis, "
            "keine Garantie — jedes System liest anders."
        ),
    },
}


def strings(lang: str) -> dict:
    return TEXT.get(lang, TEXT["en"])


def criteria_note(lang: str = "en") -> str:
    return strings(lang)["criteria"]


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


def _is_conventional(heading: str) -> bool:
    """
    Whether an ATS is likely to recognise this heading.

    The vocabulary used to live here as a second copy, and had already drifted
    from the one cv_facts used for typo detection - the same heading could be
    conventional to one check and a typo to the other. It now comes from
    guardrails/headings.py, which also means a heading repaired from icon damage
    ("S BERUFSERFAHRUNG") is recognised instead of being reported back to the
    student as unrecognisable. That false report is the one both reviewers led
    with.
    """
    entry = heading_lookup.identify(heading)
    # A heading recognised only after correcting a typo is exactly what an ATS
    # will fail on - "Educatiqn" is understood here and will not be understood
    # there - so it stays on the list of parsing risks.
    return entry is not None and entry["damage"] != "typo"


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


def _page_row(meta: dict, char_count: int, t: dict) -> dict:
    pages = meta.get("page_count")
    plural = lambda n: "s" if n > 1 else ""  # noqa: E731 - "1 Seite" / "2 Seiten"
    if pages:
        if pages <= 2:
            return {"check": t["length"], "status": GOOD,
                    "comment": t["pages_ok"].format(n=pages, s=plural(pages))}
        return {"check": t["length"], "status": ATTENTION,
                "comment": t["pages_many"].format(n=pages)}
    estimate = max(1, round(char_count / CHARS_PER_PAGE_ESTIMATE))
    return {"check": t["length"], "status": GOOD if estimate <= 2 else ATTENTION,
            "comment": t["pages_estimate"].format(n=estimate, s=plural(estimate))}


# The text-density row was removed after review: it flagged a perfectly
# well-spaced CV as "dense" on a character count, and since only extracted text
# is available, real whitespace was never observable. A measurement that cannot
# see the thing it claims to judge does not belong in the report.


def _ats_row(meta: dict, text: str, facts: dict | None, t: dict) -> dict:
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
        problems.append(t["fonts"].format(s="s" if len(fonts) > 1 else "",
                                          items=", ".join(fonts[:3])))
    elif meta.get("fonts"):
        notes.append(t["std_fonts"])

    # Career Services asked for this specifically: tell the student the headings
    # are right and something beside them did not come through, rather than
    # telling them their heading is wrong when it is not.
    # Two ways an icon shows up: as a private-use codepoint, stripped during
    # extraction and recorded there, or mapped onto an ordinary letter, which
    # only the heading lookup can spot.
    damaged = list(meta.get("icon_lines") or [])
    damaged += [s["raw_heading"] for s in (facts or {}).get("sections") or []
                if s.get("damage") == "icon" and s["raw_heading"] not in damaged]
    if damaged:
        problems.append(t["icon_headings"].format(
            items=", ".join(f'"{d.strip()}"' for d in damaged[:3])))

    headings = [h for h in heading_source if not _is_conventional(h)]
    # If the lookup recognised none of this CV's headings, the CV is very likely
    # in a language the vocabulary does not cover, and we have no basis at all
    # for saying an ATS would struggle with "FORMAÇÃO ACADÊMICA". Asserting it
    # anyway is exactly the kind of invented finding Career Services objected
    # to. Silence is the honest answer; with even one heading recognised we are
    # on familiar ground and the rest can be judged.
    recognised = len(heading_source) - len(headings)
    out_of_depth = recognised == 0 and len(heading_source) >= 3
    if headings and not out_of_depth:
        problems.append(t["headings"].format(items=", ".join(headings[:3])))
    elif not headings:
        notes.append(t["std_headings"])

    bullets = unusual_bullets(text)
    if bullets:
        problems.append(t["bullets"].format(items=" ".join(bullets[:4])))

    if meta.get("table_count"):
        problems.append(t["tables"].format(n=meta["table_count"]))

    # One image on a CV in this market is almost always the portrait photo, which
    # is conventional here and carries no text. Only a cluster of images suggests
    # content has been baked into graphics where a parser cannot reach it.
    if meta.get("image_count", 0) > 1:
        problems.append(t["images"].format(n=meta["image_count"]))

    if not problems:
        comment = (t["no_risks_with"].format(notes=", ".join(notes)) if notes
                   else t["no_risks"] + ".")
        return {"check": t["ats"], "status": GOOD, "comment": comment}

    joined = ", ".join(notes)
    # .capitalize() lowercases the rest, which mangles German nouns
    # ("Gängige schriftarten"). Only the first character may change.
    lead = (t["lead_but"].format(notes=joined[:1].upper() + joined[1:]) if notes
            else t["lead_detected"])
    return {"check": t["ats"], "status": ATTENTION,
            "comment": lead + "; ".join(problems) + "."}


def _writing_row(facts: dict, t: dict) -> dict:
    """
    Typos, mis-scanned dates and mixed British/American spelling. Career Services
    asked for this in the format check after a CV went through with "Educatiqn"
    as a heading and "Gun 2026" as a date, neither of which was mentioned.
    """
    problems = [t["typo_heading"].format(written=a, correct=b)
                for a, b in facts.get("heading_typos") or []]
    problems += [t["typo_month"].format(written=a, correct=b)
                 for a, b in facts.get("month_typos") or []]
    # Both halves are always reported, even the clean one. Listing only the
    # failures meant a CV with typos never learned its British/American spelling
    # had been checked at all.
    spelling_note = (t["spelling_mixed"].format(items=", ".join(facts["mixed_spelling"]))
                     if facts.get("mixed_spelling") else t["spelling_ok"])
    typo_note = "; ".join(str(p) for p in problems) if problems else t["typos_none"]
    status = ATTENTION if (problems or facts.get("mixed_spelling")) else GOOD
    return {"check": t["writing"], "status": status,
            "comment": t["writing_comment"].format(typos=typo_note, spelling=spelling_note)}


def run(text: str, meta: dict, facts: dict | None = None,
        lang: str = "en") -> list[dict]:
    """Returns the format-check rows: [{check, status, comment}], in `lang`."""
    t = strings(lang)
    char_count = meta.get("char_count") or len(text.strip())
    rows = [_page_row(meta, char_count, t), _ats_row(meta, text, facts, t)]
    if facts:
        rows.append(_writing_row(facts, t))
    return rows


CRITERIA_NOTE = TEXT["en"]["criteria"]
