"""
Local name/person detection, wrapping Presidio + spaCy.

Kept in its own module so pii.py stays readable and so this whole dependency can
be swapped (or removed) without touching the redaction logic. Nothing here calls
out to a network service - the models run in-process, which is the entire point:
no personal data leaves the machine.

Presidio is deliberately NOT used as a general anonymiser here. Run blindly over
a CV it also flags ORGANIZATION ("Credit Suisse", "University of St.Gallen"),
LOCATION ("Zurich") and DATE_TIME/PHONE_NUMBER on date ranges ("09.2023 -
06.2025") - all of which are exactly the content the coaching depends on.
So only PERSON is taken from it, guarded, and everything with a reliable shape
(email, phone, URL, IBAN, ID numbers) stays with the tuned patterns in pii.py.
"""

from functools import lru_cache

PERSON_SCORE_THRESHOLD = 0.6

# spaCy pipelines, one per supported CV language.
MODELS = {"en": "en_core_web_sm", "de": "de_core_news_sm"}

# A PERSON hit containing any of these is a false positive - an institution,
# not a human. spaCy's small models confuse the two regularly on CV text.
NOT_A_PERSON = {
    "university", "universität", "universitaet", "hochschule", "school", "college",
    "institute", "institut", "gmbh", "ag", "sa", "s.a.", "inc", "ltd", "llc", "plc",
    "bank", "group", "gruppe", "company", "consulting", "partners", "capital",
    "club", "association", "verein", "association", "foundation", "stiftung",
    "department", "faculty", "fakultät", "chair", "lehrstuhl", "gmbh.", "co.",
    "hsg", "eth", "ltd.", "corp", "corporation", "society", "committee",
}


class _Unavailable:
    """Stand-in when the models aren't installed, so callers degrade instead of crash."""

    available = False

    def persons(self, text: str, language: str) -> list[str]:
        return []

    def entity_strings(self, text: str, language: str, types) -> set:
        return set()


@lru_cache(maxsize=1)
def _analyzer():
    """
    Built once per process and cached. Loading both spaCy pipelines takes on the
    order of ten seconds, so this must never be constructed per rerun - Streamlit
    re-executes the script on every interaction but keeps imported modules alive,
    which is what makes an lru_cache the right place for it.
    """
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
    except ImportError:
        return _Unavailable()

    try:
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": code, "model_name": name} for code, name in MODELS.items()
            ],
        }
        engine = NlpEngineProvider(nlp_configuration=configuration).create_engine()
        return _Engine(AnalyzerEngine(nlp_engine=engine, supported_languages=list(MODELS)))
    except Exception:
        # A missing spaCy model raises at engine-construction time. Treat it the
        # same as the package being absent: degraded, not broken.
        return _Unavailable()


class _Engine:
    available = True

    def __init__(self, analyzer):
        self._analyzer = analyzer

    def persons(self, text: str, language: str) -> list[str]:
        """Person names found in `text`, longest first, already de-duplicated."""
        if not text.strip():
            return []
        language = language if language in MODELS else "en"
        try:
            results = self._analyzer.analyze(
                text=text, language=language, entities=["PERSON"]
            )
        except Exception:
            return []

        names = []
        for result in results:
            if result.score < PERSON_SCORE_THRESHOLD:
                continue
            value = text[result.start:result.end].strip(" ,.;:|·—-\t")
            if not _plausible_person(value):
                continue
            names.append(value)
        return sorted(set(names), key=len, reverse=True)


    def entity_strings(self, text: str, language: str, types) -> set:
        """
        Lower-cased full strings of the entities of the given types.

        Used to veto person hits: spaCy's small models regularly tag a place or
        an institution as a PERSON - "St. Gallen" off an address line, an NGO
        name in a volunteering entry - and propagating one of those as a name
        would blank the word out of every employer and university in the CV.
        Compared as whole strings, not tokens, because the candidate's own
        surname legitimately turns up inside an ORGANIZATION span too (a
        publication citation reads as an organisation to the model).
        """
        language = language if language in MODELS else "en"
        try:
            results = self._analyzer.analyze(text=text, language=language, entities=list(types))
        except Exception:
            return set()
        return {
            text[r.start:r.end].strip(" ,.;:|·—-\t").lower()
            for r in results
            if r.score >= PERSON_SCORE_THRESHOLD
        }


def _plausible_person(value: str) -> bool:
    if not (2 < len(value) <= 60):
        return False
    if "\n" in value:
        # spaCy will happily run a PERSON span across a line break on a CV
        # header, swallowing the street below the name. A person's name does
        # not wrap, and a multi-line span can't be matched against a line later.
        return False
    if any(ch.isdigit() for ch in value):
        return False  # "9000 St. Gallen" is a postcode, not a person
    if len(value.split()) > 5:
        return False
    words = [w.strip(".,").lower() for w in value.split()]
    if any(w in NOT_A_PERSON for w in words):
        return False
    return any(ch.isalpha() for ch in value)


def available() -> bool:
    return _analyzer().available


def detect_persons(text: str, language: str = "en") -> list[str]:
    return _analyzer().persons(text, language)


def place_and_org_strings(text: str, language: str = "en") -> set:
    """Lower-cased strings the model reads as places or institutions, not people."""
    return _analyzer().entity_strings(text, language, ("LOCATION", "ORGANIZATION", "NRP"))
