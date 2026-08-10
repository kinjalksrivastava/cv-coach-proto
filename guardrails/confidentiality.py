"""
Confidentiality/handover detection. Runs BEFORE the model is called, so
an NDA/compensation/offer mention never reaches the LLM for improvised
advice - it goes straight to app.py's confirm-then-summarize flow.
"""

import re

CONFIDENTIALITY_RE = re.compile(
    r"\b(nda|non-disclosure|non disclosure|confidential|embargo|"
    r"salary|compensation|signing bonus|base salary|total comp|"
    r"offer letter|verbal offer|return offer|"
    r"chf\s?\d|eur\s?\d|usd\s?\d|€\s?\d|\$\s?\d|"
    r"vertraulich|geheimhaltung|gehalt|jahresgehalt)\b",
    re.IGNORECASE,
)


def detect_confidentiality_trigger(text: str) -> list[str]:
    return sorted(set(m.lower() for m in CONFIDENTIALITY_RE.findall(text)))
