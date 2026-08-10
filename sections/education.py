NAME = "Education"

RULES = """EDUCATION section:
- Grades: ask whether grades are available and relevant before recommending them - \
never invent a grade or assume one is weak or strong. Prioritize the latest degree \
and current GPA; treat earlier results (bachelor's, exchange, Matura) as \
context-dependent rather than something every CV must include.
- Thesis: ask what the student actually did - dataset, method, tools, output - \
rather than inferring technical skills from the title alone.
- Exchange semester / study abroad: ask directly whether one exists before \
commenting on its absence. Accept "no" without treating it as a gap, and don't \
raise it again once the student has answered.
- Dates: if automatically detected date flags are provided in the context data \
below, you may ask about them (e.g. "I noticed two entries with overlapping \
dates - were those concurrent?"). These flags are not conclusions - a flagged \
overlap or gap can be entirely legitimate, so always ask rather than assert."""


def format_date_findings(findings: list[str]) -> str:
    if not findings:
        return ""
    lines = "\n".join(f"- {f}" for f in findings)
    return f"\nAutomatically detected date flags for Education/Experience (ask, don't assume):\n{lines}"
