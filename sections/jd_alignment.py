import re

NAME = "Job Description Alignment"

RULES = """JOB DESCRIPTION ALIGNMENT (applies whenever a target role or JD is known):
- A job description is optional. If the student hasn't provided one, ask once for a \
job title, job description, or target industry - but if none arrives after that one \
follow-up, stop asking and give structure-and-completeness feedback instead (section \
order, missing standard sections, internal consistency). Say plainly that's what \
you're doing and that role-specific feedback is available any time they add a target.
- When a job description IS known, compare CV content against it section by \
section, referencing specific requirements from the JD rather than generic advice.
- Skill or requirement mismatch: state it factually and ask whether the student has \
other relevant experience not yet listed. Never tell the student to remove, hide, or \
downplay a mismatched skill."""

# Pulled from HSG_Top_Job_Categories.docx - used only to recognize when a student's
# free-text reply names a target industry/role, so it can be captured without
# requiring the upload form to be re-opened mid-conversation.
JOB_CATEGORIES = {
    "Consulting": ["consulting", "consultant"],
    "Banking, Finance & Investment": [
        "banking", "investment bank", "corporate finance", "asset manager",
        "portfolio manager", "private equity",
    ],
    "Audit, Tax & Accounting": ["audit", "auditor", "tax associate", "accountant", "accounting"],
    "Marketing, Brand & Consumer Insights": [
        "marketing", "brand manager", "market research", "content specialist",
    ],
    "Corporate Law & In-house Legal": [
        "law firm", "legal trainee", "compliance officer", "regulatory affairs", "in-house legal",
    ],
    "Technology & Digital": [
        "data analyst", "product manager", "it consultant", "cybersecurity", "software", "tech",
    ],
    "International Organisations, Policy & Public Administration": [
        "ngo", "united nations", "embassy", "foreign ministry", "policy officer",
        "public administration", "bund",
    ],
    "Sustainability, ESG & Corporate Responsibility": [
        "sustainability", "esg", "impact investing", "csr",
    ],
    "Entrepreneurship & Start-ups": [
        "founder's associate", "startup", "start-up", "venture capital", "venture analyst",
    ],
    "Economics, Research & Trading": [
        "economic research", "equity research", "credit research", "sales & trading", "trading analyst",
    ],
    "Business Development & Sales": [
        "business development", "sales development", "account executive", "key account manager",
    ],
    "Graduate Training Programmes": ["graduate trainee", "graduate programme", "graduate program", "rotational"],
}

_ALL_KEYWORDS = [
    (kw, category) for category, kws in JOB_CATEGORIES.items() for kw in kws
]


def detect_target_role_mention(text: str) -> str | None:
    """
    Best-effort: returns the matched category name if the student's free-text
    message plausibly names a target industry/role, else None. Deliberately
    simple substring matching - a false negative just means the student is
    asked again or falls into the structure-only path, which is a safe default;
    a false positive just means the bot treats a passing mention as the target,
    which the student can always correct.
    """
    lowered = text.lower()
    for kw, category in _ALL_KEYWORDS:
        if kw in lowered:
            return category
    return None
