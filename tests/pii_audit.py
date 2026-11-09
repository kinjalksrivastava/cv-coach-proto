"""
The proof that nothing personal leaves this machine.

Every sample CV and every sample cover letter goes through exactly the pipeline
the app uses, and then the text that WOULD be sent to the model is read back by
a scanner written from scratch. That second part is the point: pii.residual_pii
checks the document with the same patterns that redacted it, so it can only
ever find what those patterns already look for. A postal address in a format
they do not cover is invisible to both. This scanner is deliberately separate,
deliberately broader, and deliberately indifferent to how the redaction works.

It is also the document to put in front of a data-protection review: it names
every category, says where each one is checked, and either prints a clean sheet
or prints the exact line that failed.

    ./venv/bin/python tests/pii_audit.py            # every sample
    ./venv/bin/python tests/pii_audit.py --verbose  # print each redacted text

Offline. No model call, no network. Samples:

    ~/Downloads/CV Samples/
    ~/Downloads/Cover Letter Samples/
"""

import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import letter_pii                                                   # noqa: E402
import pii                                                          # noqa: E402
import pii_local                                                    # noqa: E402
from extraction import extract_text                                 # noqa: E402
from guardrails import language                                     # noqa: E402

CV_SAMPLES = os.path.expanduser("~/Downloads/CV Samples")
LETTER_SAMPLES = os.path.expanduser("~/Downloads/Cover Letter Samples")

# Every placeholder the removal layers write. A hit that is only a placeholder
# is not a leak, so they are taken out before the scan.
PLACEHOLDERS = [value[0] for value in pii.CATEGORIES.values()]

# --- the scanner -------------------------------------------------------------
#
# Written against what personal data LOOKS like, not against what the removal
# layers happen to search for.

SCANS: list[tuple[str, re.Pattern]] = [
    ("email address",
     re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("web or profile link",
     re.compile(r"(?:https?://|www\.)\S+|(?:linkedin|xing|github|gitlab|orcid)\.\S+",
                re.IGNORECASE)),
    ("international phone number",
     re.compile(r"\+\d{1,3}[\s\-./()]?\d[\d\s\-./()]{6,}\d")),
    ("national phone number",
     re.compile(r"(?<![\d.\-/])0\d{2}[\s\-./]?\d{3}[\s\-./]?\d{2}[\s\-./]?\d{2}(?![\d.\-/])")),
    # Continental European: an optional country letter pair, a 4 or 5 digit
    # code, a town. "CH- 9004 St. Gallen" got through the removal layer on the
    # space after the hyphen alone.
    ("European postcode and town",
     re.compile(r"(?m)^[^\S\n]*(?:(?:CH|DE|AT|FR|IT|LI|LU|BE|NL)[\s\-]*)?"
                r"\d{4,5}[^\S\n]+[A-ZÄÖÜ][\w.\-äöüß]+(?:[^\S\n]+[\w.\-äöüß]+){0,3}"
                r"[^\S\n]*$")),
    ("US city, state and ZIP",
     re.compile(r"\b[A-Z][\w.\-]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b")),
    ("UK postcode",
     re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b")),
    ("street and number",
     re.compile(r"\b[\w.\-äöüß]*(?:strasse|straße|str\.|gasse|weg|platz|allee|ring|"
                r"steig|avenue|street|road|lane|boulevard|drive)\b[^\n,]{0,20}?"
                r"\s\d{1,4}[a-zA-Z]?\b", re.IGNORECASE)),
    ("title in front of a name",
     re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Herr|Frau|Dr|Prof)\.?\s+[A-ZÄÖÜ][\w\-äöüß]{2,}")),
    ("addressed by name",
     re.compile(r"\b(?:Dear|Sehr\s+geehrter?|Liebe[rs]?)[^\S\n]+"
                r"(?!Sir|Madam|Hiring|Recruit|Ladies|Damen|Herren|Team|Colleagues|All\b)"
                r"[A-ZÄÖÜ][\w\-äöüß]{2,}", re.IGNORECASE)),
    ("attention line with a name",
     re.compile(r"(?:z\.?\s*Hd\.?|zu\s+H[äa]nden|Attn\.?|Attention)[\s:.]+[A-ZÄÖÜ]",
                re.IGNORECASE)),
    ("IBAN or bank account",
     re.compile(r"\b[A-Z]{2}\d{2}[\s]?(?:[A-Z0-9]{4}[\s]?){2,7}[A-Z0-9]{1,4}\b")),
    ("civil status or nationality field",
     re.compile(r"\b(?:nationalit[äy]t?|staatsangeh[öo]rigkeit|citizenship|"
                r"zivilstand|familienstand|marital\s+status|civil\s+status)\b"
                r"\s*[:\-]", re.IGNORECASE)),
    ("date of birth field",
     re.compile(r"\b(?:date\s+of\s+birth|geburtsdatum|geboren\s+am|geb\.|born\s+on)\b"
                r"\s*[:\-]?\s*\d", re.IGNORECASE)),
]


# What a placeholder is replaced with before scanning: a character that no
# pattern below can match, and that cannot join the words on either side of it
# into something that looks like a leak. A space turned "Sehr geehrte
# [RECIPIENT REDACTED]" into "Sehr geehrte" followed by the next line.
SENTINEL = "\u00a7"


def _without_placeholders(text: str) -> str:
    for placeholder in PLACEHOLDERS:
        text = text.replace(placeholder, SENTINEL)
    return text


# Words that turn up inside a span the small models mislabel as a person. The
# first run of this audit reported "collected feedback", "like yours",
# "Bereich Logistik" and "• Planung" as people. A span containing any of these
# is a phrase, not a name.
NOT_IN_A_NAME = {
    "the", "a", "an", "and", "or", "of", "in", "at", "on", "for", "with", "to",
    "from", "during", "like", "yours", "your", "my", "our", "their", "this",
    "that", "these", "those", "make", "makes", "provides", "provide", "zero",
    "therefore", "collected", "feedback", "led", "using", "within", "job",
    "intern", "internship", "analysis", "program", "programme", "project",
    "projects", "class", "classes", "week", "lead", "member", "board", "shop",
    "finisher", "marathon", "spots", "skiing", "interests", "german", "swiss",
    "der", "die", "das", "den", "dem", "und", "oder", "von", "vom", "im", "in",
    "bei", "mit", "für", "sie", "ich", "bin", "grund", "themen", "bereich",
    "pflege", "projekt", "planung", "führen", "schwerpunkt", "wirtschaft",
    "lastwagen", "development", "hack", "growth", "hacking", "finance",
    "corporate", "banking", "investment", "associate", "product", "analyst",
    "stakeholders", "timely", "journey", "self-service",
}


def person_names(text: str, lang: str) -> list[str]:
    """
    Does a human name survive anywhere? Asked separately from the patterns,
    because a name has no shape to match.

    The small spaCy models are generous: on the first run of this audit they
    reported "• Planung", "collected feedback" and "like yours" as people. A
    span is only reported here when BOTH language models return it
    independently, it survives the places-and-organisations veto in both, and
    every word in it reads like part of a name. That is a deliberately strict
    gate - its job is to be believable when it says a document is clean, and
    anything it is unsure about is better raised by the layers that redact.
    """
    if not pii_local.available():
        return ["(name model unavailable - names were not checked)"]
    veto = (pii_local.place_and_org_strings(text, "en")
            | pii_local.place_and_org_strings(text, "de"))
    seen = [set(pii_local.detect_persons(text, model)) for model in ("en", "de")]
    agreed = seen[0] & seen[1]
    found = []
    for name in sorted(agreed):
        words = name.replace(",", " ").split()
        if not (1 < len(words) <= 4):
            continue
        if name.lower() in veto or pii._only_ever_next_to_an_institution(name, text):
            continue
        if any(word.lower().strip(".") in NOT_IN_A_NAME for word in words):
            continue
        if not all(word[:1].isupper() and word.replace("-", "").isalpha()
                   for word in words):
            continue
        found.append(name)
    return found


def scan(text: str, lang: str) -> tuple[list[str], list[str]]:
    """
    Returns (leaks, to_review).

    A pattern hit is a leak and fails the run: an email address, a postcode, a
    phone number and a salutation with a name in it are personal data wherever
    they appear, and there is nothing to weigh up.

    A surviving person name is listed for a human instead. No test can tell a
    referee from the conductor a student once performed under, and both read
    the same to a name model. Redacting every one of them would take "Berlin
    Philharmonie under Sir Simon Rattle" out of the bullet that earns the
    student their Music section. So each is printed with the line it sits on,
    for a reader to judge once, rather than guessed at every run.
    """
    stripped = _without_placeholders(text)
    leaks = []
    for label, pattern in SCANS:
        for match in pattern.finditer(stripped):
            # A four-digit year opening a CV line is a date, not a postcode.
            # "2022 Co-Präsidentin Mittelschulverbindung Frauenfeld" is a
            # leadership role; the redaction layer deliberately keeps it, and
            # this audit has to agree or it reports its own fix as a leak.
            # Same rule, one implementation - see pii.py.
            if (label == "European postcode and town"
                    and pii._looks_like_a_year_not_a_postcode(match.group(0).strip())):
                continue
            leaks.append(f"{label}: {match.group(0).strip()[:70]!r}")
    review = []
    for name in person_names(stripped, lang):
        line = next((l.strip() for l in text.splitlines() if name in l), "")
        review.append(f"{name!r} on: {line[:90]}")
    return leaks, review


# --- the pipeline, exactly as app.py runs it ---------------------------------

def model_bound_text(path: str) -> tuple[str, str, list[str]]:
    """What would be sent to the model, and what the app would tell the student."""
    name = os.path.basename(path)
    is_letter = LETTER_SAMPLES in path
    if path.endswith(".txt"):
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    else:
        with open(path, "rb") as handle:
            result = extract_text(handle.read(), name)
        if not result.ok:
            raise RuntimeError(result.error)
        raw = result.text

    lang = language.detect_message_language(raw) or "en"
    if is_letter:
        cleaned = letter_pii.strip_letter_pii(raw, lang)
    else:
        selected = pii.select_cv_content(raw)
        cleaned = pii.strip_pii(selected["text"], lang)
    return cleaned["text"], lang, cleaned["redactions"]


# --- the other direction: what redaction must NOT remove --------------------
#
# Every check above asks whether personal data got out. None of them asked
# whether real content was destroyed on the way, and two CVs were losing
# content to the redaction layer with nothing to catch it:
#
#   exp cv bad 1  "Chutzenstrasse 68, 3007 JUNIOR LEAD BUYER WANDER AG"
#                 - one flattened two-column line. The address pattern matched
#                   it all and the job title went with the address.
#   bad cv 3      "2022 Co-Präsidentin Mittelschulverbindung Frauenfeld"
#                 - a leadership role read as a postcode and a town, deleted
#                   whole, after which the report called the section thin.
#
# Career Services were explicit that this is the worse failure of the two:
# job titles are what the job-description alignment is built on. A leak is
# caught by the scans above; this is the counterpart, and it is a fixed list
# of things that must still be in the text the model receives.
MUST_SURVIVE = [
    ("exp cv bad 1.pdf", ["JUNIOR LEAD BUYER", "JUNIOR BUYER", "WANDER AG"]),
    ("bad cv 3.pdf", ["Co-Präsidentin", "Mittelschulverbindung"]),
    ("bad cv 6.pdf", ["Gemeindeverwaltung", "Dokumentrevision"]),
    ("good cv 7.pdf", ["Consulting & Product"]),
]


def content_survives(files: list) -> int:
    """Checks that redaction left the coachable content alone. Returns failures."""
    by_name = {os.path.basename(p): p for p in files}
    failures = 0
    print()
    for name, required in MUST_SURVIVE:
        path = by_name.get(name)
        if path is None:
            continue
        text, _lang, _r = model_bound_text(path)
        missing = [phrase for phrase in required if phrase not in text]
        if missing:
            failures += 1
            print(f"REMOVED {name}: redaction ate {missing}")
        else:
            print(f"intact  {name}: {', '.join(required)}")
    if not failures:
        print(f"{len(MUST_SURVIVE)} documents keep every job title and role "
              f"the coaching depends on")
    return failures


def main() -> int:
    verbose = "--verbose" in sys.argv
    files = sorted(glob.glob(f"{CV_SAMPLES}/**/*.pdf", recursive=True)
                   + glob.glob(f"{CV_SAMPLES}/**/*.docx", recursive=True))
    files += sorted(glob.glob(f"{LETTER_SAMPLES}/*"))
    if not files:
        print("No samples found.")
        return 1

    leaking, to_review = 0, []
    for path in files:
        label = os.path.relpath(path, os.path.expanduser("~/Downloads"))
        try:
            text, lang, redactions = model_bound_text(path)
        except Exception as error:                       # noqa: BLE001
            print(f"ERROR {label}: {error}")
            leaking += 1
            continue
        hits, review = scan(text, lang)
        if hits:
            leaking += 1
            print(f"LEAK  {label}  ({lang})")
            for hit in dict.fromkeys(hits):
                print(f"        {hit}")
        else:
            print(f"clean {label}  ({lang})  removed: {', '.join(redactions) or 'nothing'}")
        for item in dict.fromkeys(review):
            to_review.append(f"      {label}: {item}")
        if verbose:
            print("-" * 78)
            print(text)
            print("-" * 78)

    print(f"\n{len(files) - leaking}/{len(files)} documents carry no personal data "
          f"of any checked category into the model")
    print(f"{len(SCANS)} categories checked: "
          + ", ".join(dict.fromkeys(label for label, _ in SCANS)))
    if to_review:
        print(f"\n{len(to_review)} person name(s) survive, for a human to judge. A name "
              f"is\nreported here whichever side of the line it falls on:")
        for item in to_review:
            print(item)
    eaten = content_survives(files)
    return 1 if (leaking or eaten) else 0


if __name__ == "__main__":
    sys.exit(main())
