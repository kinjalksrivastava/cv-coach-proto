"""
Language handling per the spec: ask English or German once at session
start, treat that as the default, but if the student then actually
writes in the other language, follow what they write from that point
on rather than sticking to the stated preference.

Only English and German are in scope (per the requirements doc). A
message detected as some other language doesn't trigger a switch -
there's nowhere sensible to switch to - it just keeps the current
effective language.
"""

import threading

from langdetect import DetectorFactory, LangDetectException, detect

# langdetect seeds a shared, global, random detector. Two things follow, and
# both of them bit us:
#
#   - the same CV can detect differently on two runs, because the seed moves;
#   - the state is global and NOT thread-safe, so two detections running at
#     once corrupt each other.
#
# tests/full_sweep.py reads five CVs in parallel, and a German CV that detects
# "de" eight times out of eight on its own came back "en" inside the sweep -
# producing an entirely English report for a German student. Streamlit serves
# concurrent users, so this is not only a test artefact: two students uploading
# at the same moment could be given each other's language. Both reviewers have
# reported reports in the wrong language, and the string tables we translated
# were only half the cause.
#
# A fixed seed makes one detection repeatable; the lock is what makes it
# correct when more than one runs at a time.
DetectorFactory.seed = 0
_DETECT_LOCK = threading.Lock()

SUPPORTED = {"en": "English", "de": "Deutsch"}

# Below this length, langdetect is unreliable (a "ja" or "yes" reply
# can misfire either way) - too short to trust, so don't switch on it.
MIN_CHARS_FOR_DETECTION = 15


def detect_message_language(text: str) -> str | None:
    """Returns 'en' or 'de' if confidently detected and in scope, else None."""
    if len(text.strip()) < MIN_CHARS_FOR_DETECTION:
        return None
    try:
        with _DETECT_LOCK:
            code = detect(text)
    except LangDetectException:
        return None
    return code if code in SUPPORTED else None


def resolve_effective_language(stated_pref: str, current_effective: str, latest_message: str) -> str:
    """
    stated_pref: the language chosen upfront ('en' or 'de').
    current_effective: the language actually in use so far this session
        (starts equal to stated_pref, may have already drifted).
    latest_message: the student's most recent message.

    Returns the language to respond in for this turn. Only moves away
    from the current effective language on a confident detection of the
    OTHER supported language - never on a null/uncertain detection, so
    a short "ok" or "danke" doesn't bounce the session back and forth.
    """
    detected = detect_message_language(latest_message)
    if detected and detected != current_effective:
        return detected
    return current_effective
