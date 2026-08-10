"""
Guardrails that apply everywhere, regardless of which CV section the
conversation is about. Two directions:

  - Input side: rewrite-pressure detection, run before the model, adds
    a reminder into that turn's context.
  - Output side: score check and a soft rewrite-output check, both run
    AFTER the model responds. The score check is reliable enough to
    force a regeneration. The rewrite check is a heuristic (see the
    honesty note in its docstring) - it flags for a stronger nudge on
    retry, but a persistent, well-worded jailbreak can still slip past
    a regex. This is the one item flagged in PROJECT_SPEC.md as needing
    a harder block eventually.
"""

import re

SCORE_RE = re.compile(
    r"(\b\d{1,3}\s*/\s*(10|100)\b|"
    r"\bout of (10|100)\b|"
    r"\bscore of\b|\brating of\b|\bi'?d rate\b|\brate it\b|"
    r"\b\d{1,3}\s?%\s?(complete|strong|ready)\b|"
    r"\bgrade:\s?\w)",
    re.IGNORECASE,
)

REWRITE_REQUEST_RE = re.compile(
    r"(write it for me|rewrite (it|this|that)|just give me the (wording|words|bullet)|"
    r"can you word it|do it for me|give me an example bullet|"
    r"just this once|give me a draft)",
    re.IGNORECASE,
)

# Heuristic only: looks for the model presenting what reads like a
# ready-to-paste bullet it authored, rather than a question. Cheap
# false positives are acceptable (over-triggers a regeneration nudge);
# cheap false negatives are not fully avoidable with regex alone.
REWRITE_OUTPUT_RE = re.compile(
    r"(here'?s a (rewritten|revised|new) (version|bullet|line)|"
    r"you could (write|say|put)\s*[:\-]|"
    r"try this\s*[:\-]|"
    r"suggested wording\s*[:\-])",
    re.IGNORECASE,
)


def contains_rewrite_pressure(text: str) -> bool:
    return bool(REWRITE_REQUEST_RE.search(text))


def output_score_check(response_text: str) -> bool:
    """True if the response looks like it scored the CV."""
    return bool(SCORE_RE.search(response_text))


def output_rewrite_check(response_text: str) -> bool:
    """True if the response looks like it drafted text for the student."""
    return bool(REWRITE_OUTPUT_RE.search(response_text))


REWRITE_PRESSURE_REMINDER = (
    "[Internal reminder: the student's last message pressed you to write or rewrite "
    "text for them. Do not comply. Redirect to the relevant section's questions so "
    "they draft it themselves.]"
)

SCORE_RETRY_REMINDER = (
    "[Internal reminder: your previous draft of this response contained something "
    "that reads as a score, rating, or numeric judgment of the CV. Regenerate the "
    "response without any score, rating, percentage, or good/bad label.]"
)

REWRITE_RETRY_REMINDER = (
    "[Internal reminder: your previous draft of this response reads like you wrote "
    "or drafted CV text for the student. Regenerate it as a question or a short list "
    "of things to consider instead - never as text they could paste directly.]"
)
