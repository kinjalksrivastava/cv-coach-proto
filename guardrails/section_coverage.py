"""
Best-effort detection of which CV sections actually exist in this
student's document, so the bot can be told what the full checklist is
for THIS CV (not every CV has a thesis or extracurriculars) and
proactively work through it rather than only answering what's asked.

Keyword-based, EN + DE. Same honesty caveat as the rest of the regex
heuristics in this project: good enough to build a checklist to guide
the conversation, not a guaranteed-complete parse of every CV layout.
"""

import re

# Ordered so the checklist reads in a natural CV order when detected.
SECTION_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Education", ["education", "ausbildung", "studium", "akademische"]),
    ("Experience", ["professional experience", "work experience", "experience",
                     "berufserfahrung", "praktische erfahrung"]),
    ("Extracurricular & Interests", ["extracurricular", "interests", "hobbies",
                                       "ausserschulisch", "außerschulisch", "freizeit", "interessen"]),
    ("Skills & Languages", ["skills", "languages", "sprachen", "kenntnisse", "fähigkeiten"]),
]


def detect_sections(cv_text: str) -> list[str]:
    """Returns canonical section names whose header keywords appear in the CV text."""
    lowered = cv_text.lower()
    found = []
    for name, keywords in SECTION_KEYWORDS:
        if any(re.search(r"\b" + re.escape(kw) + r"\b", lowered) for kw in keywords):
            found.append(name)
    return found
