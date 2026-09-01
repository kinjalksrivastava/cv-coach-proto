"""
Personal-data stripping for extracted CV / job description text.

Everything in this module runs LOCALLY. No part of the document is sent anywhere
to work out what the personal data is - that was the point of the change: the
personal data must never reach a third-party model, because removing it is the
privacy guarantee, not a downstream nicety.

Three layers, in this order:

  1. The contact block. Everything above the CV's first section heading is,
     on essentially every CV, name + address + phone + email + links + date of
     birth and nothing the coaching needs. Contact-shaped lines there are
     removed outright rather than redacted field by field, so nothing personal
     survives a pattern that didn't happen to match. A non-contact line (a
     tagline, a professional title) is kept.

  2. Names, via a local spaCy NER model wrapped in pii_local.py. This is the
     layer a regex genuinely cannot do - "Anna Meier" and "Nestle S.A." are the
     same shape and only meaning separates them. Once a name is known, each of
     its parts is then removed everywhere else in the document too, which is how
     a name in a footer or a publication citation gets caught.

  3. Deterministic patterns for everything with a reliable shape: email, phone
     (guarded against CV date ranges), LinkedIn/GitHub/personal links, IBAN,
     matriculation/passport/AHV numbers, date of birth, nationality, civil
     status, postal addresses inline and split across lines.

If the local NER model isn't installed, layers 1 and 3 still run and the result
reports degraded=True, so the interface can say so rather than quietly doing
less than it claims.
"""

import re

import pii_local


# --- what each category is called, and what replaces it ----------------------

CATEGORIES: dict[str, tuple[str, str]] = {
    # key             placeholder                        human label
    "name":           ("[NAME REDACTED]",                "name"),
    "email":          ("[EMAIL REDACTED]",               "email"),
    "phone":          ("[PHONE REDACTED]",               "phone"),
    "address":        ("[ADDRESS REDACTED]",             "postal address"),
    "profile_url":    ("[PROFILE LINK REDACTED]",        "profile / personal link"),
    "date_of_birth":  ("[DATE OF BIRTH REDACTED]",       "date of birth"),
    "place_of_birth": ("[PLACE OF BIRTH REDACTED]",      "place of birth"),
    "nationality":    ("[NATIONALITY REDACTED]",         "nationality"),
    "marital_status": ("[CIVIL STATUS REDACTED]",        "civil status"),
    "id_number":      ("[ID NUMBER REDACTED]",           "ID / matriculation number"),
    "bank":           ("[BANK DETAILS REDACTED]",        "bank details"),
    "referee":        ("[REFEREE DETAILS REDACTED]",     "referee details"),
    "contact_block":  ("[CONTACT DETAILS REMOVED]",       "contact block (name, address, links)"),
    "other":          ("[PERSONAL DETAIL REDACTED]",     "other personal detail"),
}


def _placeholder(category: str) -> str:
    return CATEGORIES.get(category, CATEGORIES["other"])[0]


def _label(category: str) -> str:
    return CATEGORIES.get(category, CATEGORIES["other"])[1]


# --- layer 1: deterministic patterns -----------------------------------------

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Profile and personal links, with or without a scheme. Ordered widest-first so
# a full URL is consumed before a bare handle inside it can match.
PROFILE_RE = re.compile(
    r"((https?://)?(www\.)?"
    r"(linkedin\.com/(in|pub)/[\w\-%.]+"
    r"|xing\.com/profile/[\w\-%.]+"
    r"|github\.com/[\w\-]+"
    r"|gitlab\.com/[\w\-]+"
    r"|orcid\.org/[\dX\-]+"
    r"|scholar\.google\.[a-z.]+/citations\?[^\s]+"
    r"|researchgate\.net/profile/[\w\-%.]+"
    r"|behance\.net/[\w\-]+"
    r"|dribbble\.com/[\w\-]+"
    r"|medium\.com/@[\w\-.]+"
    r"|(twitter|x)\.com/[\w]+"
    r"|instagram\.com/[\w\-.]+"
    r"|facebook\.com/[\w\-.]+"
    r"|t\.me/[\w\-]+)/?)",
    re.IGNORECASE,
)

# A bare handle on a contact line ("LinkedIn: anna-meier-1234").
HANDLE_LINE_RE = re.compile(
    r"(?im)^(?P<key>\s*(linkedin|xing|github|gitlab|orcid|twitter|instagram|"
    r"portfolio|website|homepage|blog)\s*[:\-–|]\s*)(?P<val>\S.*)$"
)

IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[\s]?(?:[A-Z0-9]{4}[\s]?){2,7}[A-Z0-9]{1,4}\b")

ID_NUMBER_RE = re.compile(
    r"(?im)^.*\b(matriculation( number| no\.?)?|matrikelnummer|student (id|number)|"
    r"ahv|social security|passport (no\.?|number)|ausweisnummer|"
    r"driver'?s licen[cs]e|führerausweis|personalnummer)\b.*$"
)

DOB_KEYWORDS = re.compile(
    r"(date of birth|d\.o\.b\.?|\bdob\b|born on|born in|geburtsdatum|geboren am|geb\.)",
    re.IGNORECASE,
)
DATE_NEAR_RE = re.compile(
    r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}|\d{4}[./\-]\d{1,2}[./\-]\d{1,2}|\d{1,2}\s+"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)"
    r"[a-z]*\.?\s+\d{4})",
    re.IGNORECASE,
)

NATIONALITY_RE = re.compile(
    r"(?im)^.*\b(nationality|staatsangehörigkeit|citizenship|nationalität|"
    r"heimatort|place of origin)\b\s*[:\-–]?\s*.*$"
)
MARITAL_RE = re.compile(
    r"(?im)^.*\b(marital status|civil status|familienstand|zivilstand)\b\s*[:\-–]?\s*.*$"
)
MARITAL_WORDS_RE = re.compile(
    r"\b(verheiratet|ledig|geschieden|verwitwet)\b", re.IGNORECASE
)

# A street line: number-then-name or name-then-number, plus a 4-5 digit postal
# code line. Both are only treated as an address when they sit near a postcode,
# so a project called "Bahnhofstrasse 12" in prose isn't nuked.
POSTCODE_CITY_RE = re.compile(
    r"(?m)^\s*(CH|DE|AT|FR|IT|LI)?[\s\-]?\d{4,5}\s+[A-ZÄÖÜ][\w.\-äöüß]+"
    r"(\s+[\w.\-äöüß]+)*\s*$"
)
STREET_RE = re.compile(
    r"(?m)^\s*([A-ZÄÖÜ][\w.\-äöüß]*\s?)"
    r"(straße|strasse|str\.|gasse|weg|platz|allee|ring|steig|avenue|street|road|lane)"
    r"[\w\s.\-]*\s+\d+[a-zA-Z]?\s*$",
    re.IGNORECASE,
)
# The same address written inline on one contact line, which is at least as
# common on a CV as the two-line form.
INLINE_ADDRESS_RE = re.compile(
    r"[A-ZÄÖÜ][\w.\-äöüß]*\s?"
    r"(straße|strasse|str\.|gasse|weg|platz|allee|ring|steig|avenue|street|road|lane)"
    r"[\w\s.\-]*\s+\d+[a-zA-Z]?\s*,\s*"
    r"(CH|DE|AT|FR|IT|LI)?[\s\-]?\d{4,5}\s+[A-ZÄÖÜ][\w.\-äöüß]+"
    r"([\s,]+[A-ZÄÖÜ][\w.\-äöüß]+)*",
    re.IGNORECASE,
)

PHONE_CONTEXT_RE = re.compile(
    r"\b(tel|telephone|phone|mobile|mobil|handy|cell|fon|natel|whatsapp)\b", re.IGNORECASE
)
PHONE_CANDIDATE_RE = re.compile(
    r"(?<![\w])(\+\d{1,3}[\s./\-]?)?(\(?\d{2,4}\)?[\s./\-]?){2,6}\d{2,4}(?![\w])"
)
YEAR_RANGE_RE = re.compile(r"^(19|20)\d{2}\s*[-–—/.]\s*(19|20)\d{2}$")


def _is_phone(matched: str, line: str) -> bool:
    """
    Guards against the classic false positive: a CV date range like
    "2019 - 2022" is digit-for-digit indistinguishable from a phone number,
    and redacting it would destroy exactly the content the date guardrail and
    the Experience coaching rules depend on.
    """
    text = matched.strip()
    digits = re.sub(r"\D", "", text)
    if not (7 <= len(digits) <= 15):
        return False
    if YEAR_RANGE_RE.match(text):
        return False
    if re.fullmatch(r"\d{7,}", text) and not PHONE_CONTEXT_RE.search(line):
        return False  # a bare digit run with no phone context: could be anything
    if text.startswith("+") or text.startswith("00") or text.startswith("0"):
        return True
    if PHONE_CONTEXT_RE.search(line):
        return True
    return len(re.findall(r"[\s./\-()]", text)) >= 2


def _line_of(text: str, index: int) -> str:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    return text[start:] if end == -1 else text[start:end]


def _sub_phones(text: str) -> tuple[str, bool]:
    hits = []
    for m in PHONE_CANDIDATE_RE.finditer(text):
        if _is_phone(m.group(0), _line_of(text, m.start())):
            hits.append((m.start(), m.end()))
    if not hits:
        return text, False
    out, cursor = [], 0
    for start, end in hits:
        out.append(text[cursor:start])
        out.append(_placeholder("phone"))
        cursor = end
    out.append(text[cursor:])
    return "".join(out), True


def _sub_address(text: str) -> tuple[str, bool]:
    """
    A street name alone is not enough to act on - "Bahnhofstrasse 12" could be a
    client site in a bullet point. Only redacts when a postal code is present
    too, either inline on the same line or on its own line beneath.
    """
    working = INLINE_ADDRESS_RE.sub(_placeholder("address"), text)
    if POSTCODE_CITY_RE.search(working):
        working = POSTCODE_CITY_RE.sub(_placeholder("address"), working)
        working = STREET_RE.sub(_placeholder("address"), working)
    return working, working != text


def _deterministic_pass(text: str) -> tuple[str, list[str]]:
    working, found = text, []

    def apply(pattern, category, repl=None):
        nonlocal working
        new = pattern.sub(repl or _placeholder(category), working)
        if new != working:
            working = new
            found.append(category)

    apply(EMAIL_RE, "email")
    apply(PROFILE_RE, "profile_url")
    apply(HANDLE_LINE_RE, "profile_url", lambda m: m.group("key") + _placeholder("profile_url"))
    apply(IBAN_RE, "bank")
    apply(ID_NUMBER_RE, "id_number")

    # Date of birth must run BEFORE phones: 14.03.2001 is otherwise a plausible
    # phone-shaped digit run, and whichever pattern runs first consumes it.
    if DOB_KEYWORDS.search(working):
        lines = []
        for line in working.splitlines():
            if DOB_KEYWORDS.search(line):
                line = DATE_NEAR_RE.sub(_placeholder("date_of_birth"), line)
            lines.append(line)
        new = "\n".join(lines)
        if new != working:
            working, _ = new, found.append("date_of_birth")

    working, hit = _sub_phones(working)
    if hit:
        found.append("phone")
    working, hit = _sub_address(working)
    if hit:
        found.append("address")

    apply(NATIONALITY_RE, "nationality")
    if MARITAL_RE.search(working):
        apply(MARITAL_RE, "marital_status")
    else:
        apply(MARITAL_WORDS_RE, "marital_status")

    return working, found


# --- layer 1: the contact block ----------------------------------------------

# Vocabulary of real CV section headings, EN + DE. Used only to find where the
# contact block ends - the richer, model-driven heading parse lives in
# guardrails/section_coverage.py and runs later, on the already-redacted text.
HEADING_WORDS = (
    r"education|ausbildung|studium|akademisch\w*|"
    r"experience|berufserfahrung|praktische erfahrung|praktika|work history|employment|"
    r"profile|summary|profil|kurzprofil|about me|über mich|objective|"
    r"skills|kenntnisse|fähigkeiten|competenc\w*|it[- ]skills|edv|tools|"
    r"languages|sprachen|"
    r"publications|publikationen|research|forschung|papers|"
    r"projects|projekte|"
    r"certificat\w*|zertifikate|weiterbildung|courses|kurse|training|"
    r"awards|honou?rs|auszeichnungen|stipendien|scholarships|preise|"
    r"extracurricular\w*|ausserschulisch\w*|außerschulisch\w*|engagement|"
    r"interests|hobbies|interessen|freizeit|"
    r"volunteer\w*|ehrenamt\w*|freiwilligenarbeit|"
    r"references|referenzen|"
    r"military|zivildienst|militärdienst"
)
HEADING_RE = re.compile(rf"^\s*[\W_]*({HEADING_WORDS})\b[\s\W_]*$", re.IGNORECASE)

# How far down the document the contact block is allowed to reach. A CV whose
# first heading is on line 40 is not a CV with a 40-line contact block, it's a
# CV whose headings this pattern didn't recognise - stop rather than delete it.
MAX_CONTACT_BLOCK_LINES = 14

CONTACT_LINE_RE = re.compile(
    r"(@|\bhttps?://|\bwww\.|linkedin|xing|github|gitlab|orcid|"
    r"\btel\b|\bmobile\b|\bmobil\b|\bphone\b|\bhandy\b|\bnatel\b|"
    r"\+\d{1,3}[\s\-./]?\d|"
    r"strasse|straße|str\.|gasse|weg\b|platz\b|avenue|street|road\b|"
    r"date of birth|geburtsdatum|geboren|born|nationality|staatsangehörigkeit|"
    r"citizenship|marital|familienstand|zivilstand|"
    r"\b(CH|DE|AT)?[\s\-]?\d{4,5}\s+[A-ZÄÖÜ])",
    re.IGNORECASE,
)


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return False
    if HEADING_RE.match(stripped):
        return True
    # An all-caps short line with no contact markers is a heading by convention.
    letters = [c for c in stripped if c.isalpha()]
    return (
        len(letters) >= 3
        and all(c.isupper() for c in letters)
        and not CONTACT_LINE_RE.search(stripped)
    )


def split_contact_block(text: str) -> tuple[list[str], list[str]]:
    """
    Returns (header_lines, body_lines), split at the CV's first section heading.

    When no heading is recognised - a typo'd "Educatiqn", an unusual wording, a
    messy scan - falling back to a fixed number of lines is destructive: it hands
    the cleaner a dozen lines of real content to delete. So the fallback instead
    stops at the first line that is neither blank, nor contact-shaped, nor a
    plausible name line, which on a CV without a contact block means stopping
    immediately and removing nothing.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines[:MAX_CONTACT_BLOCK_LINES]):
        if _is_heading(line):
            return lines[:index], lines[index:]

    cut = 0
    for index, line in enumerate(lines[:MAX_CONTACT_BLOCK_LINES]):
        if line.strip() and not CONTACT_LINE_RE.search(line) and not _looks_like_a_name_line(line):
            break
        cut = index + 1
    return lines[:cut], lines[cut:]


def _clean_contact_block(header_lines: list[str], person_names: list[str]) -> tuple[list[str], bool]:
    """
    Drops the contact-shaped lines and any line carrying a detected name; keeps
    anything else (a tagline, a professional title), because that is content the
    student may well want feedback on.
    """
    kept, removed_any = [], False
    for line in header_lines:
        if not line.strip():
            kept.append(line)
            continue
        if CONTACT_LINE_RE.search(line) or any(name in line for name in person_names):
            removed_any = True
            continue
        kept.append(line)
    if removed_any:
        kept.insert(0, _placeholder("contact_block"))
    return kept, removed_any


# --- layer 1b: the name line, when the NER model doesn't see it ---------------
#
# Small spaCy models frequently miss a name that sits alone on the first line
# with no sentence around it ("Sophie Keller"), which is exactly how a CV opens.
# The contact block is being removed either way, so dropping that line is safe;
# the judgement call is whether to also blank the words out across the rest of
# the document, and that only happens when the line is shaped like a name and
# contains no word that gives it away as a title or a document heading.

ROLE_WORDS = {
    "curriculum", "vitae", "resume", "résumé", "cv", "lebenslauf", "profile", "profil",
    "student", "candidate", "analyst", "consultant", "manager", "engineer", "intern",
    "trainee", "associate", "assistant", "specialist", "developer", "researcher",
    "bachelor", "master", "msc", "mba", "phd", "doctor", "kandidat", "praktikant",
    "berater", "ingenieur", "wirtschaft", "business", "finance", "economics",
}


def _looks_like_a_name_line(line: str) -> bool:
    stripped = line.strip()
    if not (2 < len(stripped) <= 60) or any(ch.isdigit() for ch in stripped):
        return False
    if "@" in stripped or _is_heading(stripped):
        return False
    words = stripped.replace(",", " ").split()
    if not (1 < len(words) <= 4):
        return False
    if any(w.strip(".").lower() in ROLE_WORDS for w in words):
        return False
    return all(w[0].isupper() for w in words if w[0].isalpha())


def _name_line_fallback(header_lines: list[str]) -> str | None:
    for line in header_lines:
        if line.strip():
            return line.strip() if _looks_like_a_name_line(line) else None
    return None


# --- layer 2: names, detected locally ----------------------------------------

# A name part shorter than this is too collision-prone to blank out document-wide
# ("Li", "Bo", or an initial would shred unrelated words).
MIN_NAME_PART = 3


def _name_parts(names: list[str]) -> list[str]:
    parts = set()
    for name in names:
        parts.add(name)
        for token in re.split(r"[\s,]+", name):
            token = token.strip(".")
            if len(token) >= MIN_NAME_PART and token.lower() not in _NAME_PART_STOPWORDS:
                parts.add(token)
    return sorted(parts, key=len, reverse=True)


# Honorifics and particles that arrive attached to a detected name but must never
# be blanked out on their own.
_NAME_PART_STOPWORDS = {
    "dr", "prof", "professor", "herr", "frau", "mr", "mrs", "ms", "miss",
    "von", "van", "der", "den", "del", "della", "die", "das", "the", "and", "und",
    "saint", "sankt",
}


# A person hit in the BODY of a CV is only trusted with corroboration. Most body
# PERSON hits are institutions the model misread ("Kinderhilfe St. Gallen"); the
# ones that are genuinely people - referees - sit next to a title or contact
# details, or under a References heading.
TITLE_PREFIX_RE = re.compile(
    r"(dr|prof|professor|herr|frau|mr|mrs|ms|miss)\.?\s*$", re.IGNORECASE
)
REFERENCE_HEADING_RE = re.compile(r"^\s*[\W_]*(references|referenzen)\b", re.IGNORECASE)


def _body_name_is_corroborated(name: str, lines: list[str]) -> bool:
    in_references = False
    for line in lines:
        if _is_heading(line):
            in_references = bool(REFERENCE_HEADING_RE.match(line))
        position = line.find(name)
        if position == -1:
            continue
        if in_references:
            return True
        if TITLE_PREFIX_RE.search(line[:position]):
            return True
        if "@" in line or _placeholder("email") in line or _placeholder("phone") in line:
            return True
        if PHONE_CANDIDATE_RE.search(line) and any(ch.isdigit() for ch in line):
            return True
    return False


INSTITUTION_WORDS = re.compile(
    r"\b(universit(y|ä|a)t?\w*|hochschule|school|schule|institute?|institut|"
    r"gymnasium|college|akademie|academy|faculty|fakultät)\b",
    re.IGNORECASE,
)


def _only_ever_next_to_an_institution(name: str, text: str) -> bool:
    """
    "St. Gallen" reads as a person to a small NER model, and blanking it would
    take a word out of every university on the CV. If every line the candidate
    name appears on also names an institution, it is part of that institution's
    name, not a person.
    """
    lines = [line for line in text.splitlines() if name in line]
    return bool(lines) and all(INSTITUTION_WORDS.search(line) for line in lines)


def _filter_names(names: list[str], veto: set, text: str = "") -> list[str]:
    """Drops anything the model also reads as a place or an institution."""
    return [
        n for n in names
        if n.strip(" ,.;:|·—-").lower() not in veto
        and not (text and _only_ever_next_to_an_institution(n, text))
    ]


def _redact_names(text: str, names: list[str]) -> tuple[str, bool]:
    working, hit = text, False
    for part in _name_parts(names):
        pattern = re.compile(r"\b" + re.escape(part) + r"\b")
        new = pattern.sub(_placeholder("name"), working)
        if new != working:
            working, hit = new, True
    return working, hit


# --- public entry point -------------------------------------------------------


def strip_pii(text: str, language: str = "en") -> dict:
    """
    Redacts a document. Takes no client and makes no network call by design:
    nothing can send this text anywhere before it has been through here.

    Returns:
      text        - the redacted document
      redactions  - human-readable labels of what was removed, in a stable order
      categories  - the raw category keys, for callers that want them
      names_found - how many distinct person names the local model matched
      degraded    - True if the local NER model is unavailable, so names were
                    only caught inside the contact block and not elsewhere
    """
    if not text.strip():
        return {"text": text, "redactions": [], "categories": [],
                "names_found": 0, "degraded": False}

    categories: list[str] = []
    ner_available = pii_local.available()

    header_lines, body_lines = split_contact_block(text)
    header_text = "\n".join(header_lines)

    # Names are looked for in the header first (where the candidate's own name
    # almost always is) and then across the body (referees, a name in a
    # publication citation, a footer).
    names: list[str] = []
    if ner_available:
        veto = pii_local.place_and_org_strings(text, language)
        # The header name is the candidate's own: trusted, and removed everywhere
        # in the document, which is how it gets caught in a footer or a citation.
        names = _filter_names(pii_local.detect_persons(header_text, language), veto, text)
        if not names:
            # Try the other supported language before giving up: the pipelines
            # disagree on bare name lines often enough to be worth one more pass.
            other = "de" if language != "de" else "en"
            names = _filter_names(pii_local.detect_persons(header_text, other), veto, text)
        if not names:
            fallback = _name_line_fallback(header_lines)
            if fallback:
                names = [fallback]
        # A body hit needs corroboration before it is trusted - see above.
        for candidate in _filter_names(pii_local.detect_persons("\n".join(body_lines), language), veto, text):
            if candidate not in names and _body_name_is_corroborated(candidate, body_lines):
                names.append(candidate)

    header_kept, header_removed = _clean_contact_block(header_lines, names)
    if header_removed:
        categories.append("contact_block")

    working = "\n".join(header_kept + body_lines)

    if names:
        working, name_hit = _redact_names(working, names)
        if name_hit:
            categories.append("name")

    working, pattern_categories = _deterministic_pass(working)
    categories.extend(pattern_categories)

    present = set(categories)
    ordered = [c for c in CATEGORIES if c in present]
    ordered += sorted(present - set(CATEGORIES))

    return {
        "text": working,
        "redactions": [_label(c) for c in ordered],
        "categories": ordered,
        "names_found": len(names),
        "degraded": not ner_available,
    }
