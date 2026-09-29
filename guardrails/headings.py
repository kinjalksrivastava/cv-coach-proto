"""
Finding a CV's section headings, and repairing the ones the file damaged.

This module exists because of one complaint, made independently by both
reviewers, about the same underlying failure:

    "It says that «Berufserfahrung» may not be recognised even though this is the
     most common section title and I selected German during the CV upload."
    "This CV actually has Icons before each section header and I think it picks
     these up as letters when parsed."

Neither student had done anything wrong. Their CVs put a small icon next to each
heading, the icon font mapped to an ordinary Latin letter or a private-use
codepoint, and the extracted text came out as "S BERUFSERFAHRUNG" or
" AUSBILDUNG". Every downstream check then treated a perfectly standard German
heading as unrecognisable, and told the student so.

Headings used to be found by asking the model. That is right for the unusual ones
- "Selected Publications", "Board Memberships", "Case Studies" - and wrong for
the standard ones, because the standard ones are a closed vocabulary that can
simply be looked up, and a lookup does not have an off day. So both run: this
module finds every heading it recognises, the model finds the rest, and the
results are merged.

Three kinds of damage are repaired, all of them seen in real uploads:

    " BERUFSERFAHRUNG"    an icon that landed in the private-use area
    "S BERUFSERFAHRUNG"   an icon font that mapped onto a Latin letter
    "Educatiqn"           a single mistyped or mis-scanned character

The repair is reported, not hidden. Career Services asked for the student to be
told that something next to their headings did not survive the parse, because
that is worth knowing before an ATS does the same thing to their application.
"""

import re
import unicodedata
from difflib import SequenceMatcher

# Icon fonts (FontAwesome and friends) live in the Unicode private use area.
# Nothing legitimate on a CV does, so these can be stripped from the whole
# document without looking at context.
PRIVATE_USE = re.compile(r"[-\U000f0000-\U000ffffd]")

# Canonical heading vocabulary, EN and DE, mapped to the categories in
# section_coverage. Written as (display, category, variants) so the display form
# can be shown back to a student whose own heading was damaged.
VOCAB: list[tuple[str, str, tuple[str, ...]]] = [
    ("Profile", "Profile / Summary",
     ("profile", "profil", "kurzprofil", "summary", "personal profile", "about me",
      "über mich", "ueber mich", "professional summary", "career summary",
      "personal statement", "zusammenfassung", "kurzprofil")),
    ("Education", "Education",
     ("education", "ausbildung", "studium", "academic background", "akademischer werdegang",
      "akademische ausbildung", "educational background", "schulbildung", "studies",
      "academic education", "bildungsweg", "bildung", "schulische ausbildung")),
    ("Work Experience", "Experience",
     ("work experience", "professional experience", "experience", "employment",
      "employment history", "work history", "career history", "professional background",
      "berufserfahrung", "praktische erfahrung", "praktika", "berufliche erfahrung",
      "arbeitserfahrung", "berufspraxis", "praktische erfahrungen", "werdegang",
      "beruflicher werdegang", "internships", "relevant experience", "industry experience",
      "praktikum", "berufliche stationen", "erfahrung")),
    ("Publications & Research", "Publications & Research",
     ("publications", "publikationen", "research", "forschung", "research experience",
      "research papers", "working papers", "conference papers", "veröffentlichungen",
      "veroeffentlichungen", "thesis", "theses", "abschlussarbeiten", "forschungserfahrung",
      "academic work", "wissenschaftliche arbeiten")),
    ("Projects", "Projects",
     ("projects", "projekte", "case studies", "selected projects", "project experience",
      "projekterfahrung", "praxisprojekte", "student projects", "academic projects")),
    ("Skills & Languages", "Skills & Languages",
     ("skills", "kenntnisse", "fähigkeiten", "faehigkeiten", "technical skills",
      "it skills", "edv", "edv-kenntnisse", "it-kenntnisse", "computer skills",
      "languages", "sprachen", "language skills", "sprachkenntnisse", "fremdsprachen",
      "it and languages", "languages and it skills", "it & sprachen",
      "sprachen und it", "core competences", "core competencies", "kernkompetenzen",
      "competencies", "kompetenzen", "tools", "software", "digital skills",
      "sprach- und it-kenntnisse", "it", "programming", "programmierkenntnisse")),
    ("Certificates & Training", "Certifications & Training",
     ("certificates", "certifications", "zertifikate", "weiterbildung", "weiterbildungen",
      "courses", "kurse", "courses and certificates", "training", "trainings",
      "professional development", "qualifications", "qualifikationen", "fortbildung",
      "additional qualifications", "zusatzqualifikationen", "licenses")),
    ("Awards & Scholarships", "Awards & Scholarships",
     ("awards", "honors", "honours", "auszeichnungen", "scholarships", "stipendien",
      "preise", "awards and scholarships", "achievements", "erfolge", "prizes",
      "ehrungen", "auszeichnungen und stipendien")),
    ("Extracurricular Experience", "Extracurricular & Interests",
     ("extracurricular", "extracurricular activities", "extracurricular experience",
      "ausserschulische aktivitäten", "außerschulische aktivitäten",
      "ausserschulisches engagement", "engagement", "student activities",
      "ausserberufliche aktivitäten", "außerberufliche aktivitäten",
      "extra-curricular activities", "clubs and societies", "vereine",
      "mitgliedschaften", "memberships", "board memberships", "gremien")),
    ("Interests", "Extracurricular & Interests",
     ("interests", "hobbies", "interessen", "freizeit", "hobbies and interests",
      "interests and hobbies", "personal interests", "freizeitaktivitäten",
      "persönliche interessen", "hobbys", "sonstiges", "additional information",
      "weitere informationen", "sonstige informationen")),
    ("Volunteering", "Volunteering & Community",
     ("volunteering", "volunteer experience", "voluntary work", "ehrenamt",
      "ehrenamtliches engagement", "freiwilligenarbeit", "community experience",
      "community involvement", "soziales engagement", "gemeinnützige arbeit")),
    ("References", "References",
     ("references", "referenzen", "referees")),
    ("Military / Civil Service", "Other",
     ("military service", "militärdienst", "zivildienst", "wehrdienst", "rekrutenschule",
      "civil service", "national service")),
    ("Personal Details", "Other",
     ("personal details", "persönliche daten", "kontakt", "contact", "contact details",
      "persönliche angaben", "angaben zur person")),
]

# Qualifiers that do not change what a heading is.
QUALIFIERS = ("selected", "relevant", "key", "further", "additional", "other",
              "weitere", "ausgewählte", "ausgewaehlte", "sonstige", "my", "meine")

_LOOKUP: dict[str, tuple[str, str]] = {}
for _display, _category, _variants in VOCAB:
    for _variant in _variants:
        _LOOKUP.setdefault(_variant, (_display, _category))

CONNECTIVES = re.compile(r"\s*(?:&|/|\+|\band\b|\bund\b|,|\|)\s*")


def strip_private_use(text: str) -> tuple[str, list[str]]:
    """
    Remove icon-font codepoints from the whole document.

    Returns the cleaned text and the lines that carried an icon, cleaned. The
    lines are kept rather than just a count: the student is told which of their
    headings had something beside it that did not survive, and a bare number
    ("we removed 7 characters") is not something anyone can act on.

    Nothing legitimate on a CV sits in the private use area, so no context is
    needed to decide - only to report.
    """
    affected = []
    out = []
    for line in text.splitlines():
        cleaned = PRIVATE_USE.sub("", line)
        if cleaned != line:
            # An icon usually leaves a lone space or tab behind.
            cleaned = cleaned.lstrip(" \t\u00a0")
            if cleaned.strip():
                affected.append(cleaned.strip())
        out.append(cleaned)
    return "\n".join(out), affected


def normalise(value: str) -> str:
    """Casefolded, punctuation-free, umlaut-preserving form used for lookup."""
    value = unicodedata.normalize("NFC", value).strip()
    value = value.strip(" \t:.-–—*•·|")
    value = re.sub(r"\s+", " ", value)
    return value.lower()


def _match_exact(value: str) -> tuple[str, str] | None:
    if value in _LOOKUP:
        return _LOOKUP[value]
    words = value.split()
    while words and words[0] in QUALIFIERS:
        words = words[1:]
    trimmed = " ".join(words)
    if trimmed in _LOOKUP:
        return _LOOKUP[trimmed]
    # "IT & Languages", "Courses and Certificates", "Sprachen und IT": every part
    # is a known heading, so the whole is one too. The category of the first part
    # wins, which is how a student reading "Skills & Languages" would read it.
    parts = [p for p in CONNECTIVES.split(trimmed) if p]
    if len(parts) > 1 and all(p in _LOOKUP for p in parts):
        return _LOOKUP[parts[0]]
    return None


def _match_fuzzy(value: str) -> tuple[str, str] | None:
    """
    One mistyped or mis-scanned character. "Educatiqn" is the case Career
    Services sent; the ratio is deliberately tight so "Experience" never matches
    "Extracurricular".
    """
    best, best_ratio = None, 0.0
    for variant, entry in _LOOKUP.items():
        if abs(len(variant) - len(value)) > 2 or len(value) < 5:
            continue
        ratio = SequenceMatcher(None, value, variant).ratio()
        if ratio > best_ratio:
            best, best_ratio = entry, ratio
    return best if best_ratio >= 0.86 else None


# A stray glyph left by an icon: one or two characters, then a space, then the
# real heading. "S BERUFSERFAHRUNG" and "q Education" are both this.
_STRAY_PREFIX = re.compile(r"^(?P<stray>[^\s\w]{1,2}|[A-Za-z0-9]{1,2})[\s ]+(?P<rest>\S.*)$")


def identify(line: str) -> dict | None:
    """
    Decide whether one line is a section heading, repairing it if it is damaged.

    Returns None when the line is not a heading, otherwise:
        {"raw", "clean", "display", "category", "damage"}
    where `damage` is None, "icon", or "typo", and `clean` is the heading with
    the damage removed - which is what everything downstream should anchor on.
    """
    raw = line.rstrip()
    stripped = raw.strip()
    if not stripped or len(stripped) > 60:
        return None

    value = normalise(stripped)
    if not value:
        return None

    entry = _match_exact(value)
    if entry:
        return {"raw": raw, "clean": stripped.strip(" \t:"), "display": entry[0],
                "category": entry[1], "damage": None}

    # An icon that survived as an ordinary character. Only accepted when what is
    # left is an exact known heading - a fuzzy match on top of a stray-prefix
    # guess would start inventing headings out of ordinary sentences.
    match = _STRAY_PREFIX.match(stripped)
    if match:
        rest = match.group("rest")
        entry = _match_exact(normalise(rest))
        if entry:
            return {"raw": raw, "clean": rest.strip(" \t:"), "display": entry[0],
                    "category": entry[1], "damage": "icon"}

    entry = _match_fuzzy(value)
    if entry:
        return {"raw": raw, "clean": stripped.strip(" \t:"), "display": entry[0],
                "category": entry[1], "damage": "typo"}
    return None


def _heading_shaped(line: str) -> bool:
    """
    Does this line sit on the page like a heading? Used to keep `find` from
    matching the word "Education" inside a sentence.
    """
    stripped = line.strip()
    if not (2 < len(stripped) <= 60):
        return False
    if stripped[0] in "-–—•·*▪◦‣":
        return False
    # A heading does not end in a sentence, and rarely carries a year.
    if stripped.endswith((".", ";", ",")):
        return False
    if re.search(r"(?:19|20)\d{2}", stripped):
        return False
    return len(stripped.split()) <= 6


def find(text: str) -> list[dict]:
    """
    Every recognised heading in the document, in order, each with its line index.

    Deterministic and complete for the standard vocabulary - which is the half
    that was failing. Unusual headings are left to the model, which merges its
    findings with these.
    """
    found = []
    for index, line in enumerate(text.splitlines()):
        if not _heading_shaped(line):
            continue
        entry = identify(line)
        if entry:
            found.append({**entry, "index": index})
    return found


def damage_report(headings: list[dict], private_use_count: int = 0) -> list[str]:
    """
    What to tell the student about headings that did not survive the parse.

    Career Services were explicit that this should be framed as a property of the
    document, not a mistake the student made: the heading is right, something
    beside it did not come through, and an ATS will hit the same wall.
    """
    notes = []
    icons = [h for h in headings if h["damage"] == "icon"]
    if icons or private_use_count:
        names = ", ".join(f'"{h["raw"].strip()}"' for h in icons[:3])
        notes.append(
            "icon or symbol characters next to your section headings that did not "
            "survive the text extraction"
            + (f" ({names})" if names else "")
            + " — the headings themselves are fine, but an ATS reads the file the same "
              "way this tool did, so it is worth removing the icons"
        )
    return notes
