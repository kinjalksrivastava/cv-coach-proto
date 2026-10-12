"""
The layouts a CV entry can be written in, and whether the parser reads each one.

Career Services' point: this is a university-wide tool, so it has to cope with
however a student lays out their CV, not just with the layouts we happened to
test. Two bugs on their own template - a role title reported missing and an
employer period reported as concurrent with a role inside it - both came from a
layout nobody had written a test for.

So the layouts are enumerated here rather than discovered one report at a time.
Each case is one experience section written a different way, with the same facts
underneath: one employer, one or two roles, two bullets, no overlapping jobs.
Whatever the layout, the parser should find the entries, attach each bullet to
its own role, see a role title, and report no overlap.

    ./venv/bin/python tests/layouts.py

Runs offline. Add a layout here the first time a CV in the wild uses it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv_facts      # noqa: E402
import severity      # noqa: E402
from guardrails import section_coverage  # noqa: E402

# Each: (name, the experience section as it appears, how many roles it describes)
LAYOUTS = [
    ("role and employer on one line, dates right", """Work Experience
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", 1),

    ("employer line, role beneath, no role dates", """Work Experience
Beispiel AG, Zurich, Switzerland                      09/2022 - 08/2024
Analyst, Corporate Finance
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", 1),

    ("employer line dated, two roles each dated", """Work Experience
Beispiel AG, Zurich, Switzerland                      09/2020 - 08/2024
Senior Analyst                                        09/2022 - 08/2024
- Rebuilt the monthly reporting pack, cutting two days off the close
Analyst                                               09/2020 - 08/2022
- Ran reconciliations across four entities
""", 2),

    ("two roles stacked, bullets under the pair", """Work Experience
Beispiel AG, Zurich
Senior Analyst                                        09/2022 - 08/2024
Analyst                                               09/2020 - 08/2022
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", 2),

    ("dates first, left column", """Work Experience
09/2022 - 08/2024    Beispiel AG, Zurich
                     Analyst, Corporate Finance
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", 1),

    ("role, employer and dates on three lines", """Work Experience
Analyst, Corporate Finance
Beispiel AG, Zurich, Switzerland
09/2022 - 08/2024
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", 1),

    ("dates in brackets after the role", """Work Experience
Analyst, Corporate Finance at Beispiel AG, Zurich (09/2022 - 08/2024)
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", 1),

    ("employer in caps, role in sentence case beneath", """Work Experience
BEISPIEL AG                                           09/2022 - 08/2024
Analyst, Corporate Finance, Zurich
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", 1),

    ("pipe separated, dates at the end", """Work Experience
Beispiel AG | Analyst, Corporate Finance | Zurich | 09/2022 - 08/2024
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", 1),

    ("em-dash separated, German, present role", """Berufserfahrung
Beispiel AG, Zürich — Analyst Corporate Finance        09/2022 – heute
- Aufbau des monatlichen Reportings, drei Tage schnellerer Abschluss
- Durchführung der Abstimmungen über vier Gesellschaften
""", 1),

    ("tab separated with a trailing location line", """Work Experience
Beispiel AG\tAnalyst, Corporate Finance\t09/2022 - 08/2024
Zurich, Switzerland
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", 1),

    ("no bullet glyph at all, plain indented lines", """Work Experience
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
    Rebuilt the monthly reporting pack, cutting two days off the close
    Ran reconciliations across four entities
""", 1),

    ("arrow bullets", """Work Experience
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
→ Rebuilt the monthly reporting pack, cutting two days off the close
→ Ran reconciliations across four entities
""", 1),

    ("two-column extraction: all dates first, then all content", """Work Experience
09/2022 - 08/2024
09/2019 - 06/2021
Analyst, Beispiel AG, Zurich
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", 1),

    ("table extraction, one cell per line", """Work Experience
Beispiel AG
Analyst, Corporate Finance
Zurich, Switzerland
09/2022
08/2024
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", 1),

    ("open-ended German date, no end", """Berufserfahrung
Analyst Corporate Finance, Beispiel AG, Zürich        seit 09/2022
- Aufbau des monatlichen Reportings, drei Tage schnellerer Abschluss
- Durchführung der Abstimmungen über vier Gesellschaften
""", 1),

    ("everything in capitals", """WORK EXPERIENCE
ANALYST, BEISPIEL AG, ZURICH                          09/2022 - 08/2024
- REBUILT THE MONTHLY REPORTING PACK, CUTTING TWO DAYS OFF THE CLOSE
- RAN RECONCILIATIONS ACROSS FOUR ENTITIES
""", 1),

    ("oldest first, no blank lines between entries", """Work Experience
Intern, Andere AG, Basel                              06/2019 - 08/2019
- Supported the quarterly close
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
- Rebuilt the monthly reporting pack, cutting two days off the close
""", 2),

    ("freelance entry with no employer", """Work Experience
Freelance data analyst                                09/2022 - 08/2024
- Rebuilt the monthly reporting pack for three small clients
- Ran reconciliations across four entities
""", 1),

    ("bullets written with a middle dot", """Work Experience
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
• Rebuilt the monthly reporting pack, cutting two days off the close
• Ran reconciliations across four entities
""", 1),
]

EDUCATION = """
Education
MA in Banking and Finance, University of St. Gallen   09/2019 - 06/2021
- Major in Corporate Finance
"""


def check(name: str, section: str, roles: int) -> list[str]:
    text = section + EDUCATION
    sections = section_coverage.detect_sections(text)
    facts = cv_facts.analyse(text, {"page_count": 1}, sections)
    issues = {i["key"] for i in severity.assess(facts)["all_issues"]}
    experience = next((s for s in facts["sections"]
                       if s["category"] == "Experience"), None)

    problems = []
    if experience is None:
        return ["the experience section was not found at all"]
    if not experience["entry_count"]:
        problems.append("no entries found")
    if experience["bullet_count"] < 2:
        problems.append(f"{experience['bullet_count']} bullets found, expected 2")
    if experience["entries_without_title"]:
        problems.append(f"role title reported missing: "
                        f"{experience['entries_without_title'][0][:44]!r}")
    if experience["entries_without_detail"]:
        problems.append(f"entry reported as having no description: "
                        f"{experience['entries_without_detail'][0][:44]!r}")
    if "date_overlap" in issues:
        problems.append("a false overlap was reported")
    if "no_bullets_anywhere" in issues:
        problems.append("reported as having no bullets anywhere")
    return problems


def main() -> int:
    failed = 0
    for name, section, roles in LAYOUTS:
        problems = check(name, section, roles)
        if problems:
            failed += 1
            print(f"FAIL  {name}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"ok    {name}")
    print(f"\n{len(LAYOUTS) - failed}/{len(LAYOUTS)} layouts read correctly")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
