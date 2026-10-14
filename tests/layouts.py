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

# --- education, which stacks differently from experience ---------------------
# Layouts taken from how CVs are actually written rather than invented: degree
# first then school, school first then degree, the minimalist one-line form,
# an expected graduation date, a grade on the degree line, and the Swiss and
# German conventions Career Services' own samples use.
EDUCATION_LAYOUTS = [
    ("degree first, school and dates beneath", """Education
MA in Banking and Finance
University of St. Gallen, St. Gallen, Switzerland     09/2022 - 06/2024
- Grade average 5.4 / 6.0
- Exchange semester at Bocconi, Milan
""", 2),

    ("school and dates on one line, degree beneath", """Education
University of St. Gallen, Switzerland                 09/2022 - 06/2024
MA in Banking and Finance, major in Corporate Finance
- Grade average 5.4 / 6.0
- Thesis on covenant pricing in mid-market lending
""", 2),

    ("degree, school and dates pipe separated", """Education
MA in Banking and Finance | University of St. Gallen | 09/2022 - 06/2024
- Grade average 5.4 / 6.0
- Exchange semester at Bocconi, Milan
""", 2),

    ("expected graduation", """Education
MA in Banking and Finance, University of St. Gallen   09/2022 - expected 06/2026
- Grade average 5.4 / 6.0
- Thesis on covenant pricing in mid-market lending
""", 2),

    ("grade on the degree line itself", """Education
University of St. Gallen | MA Banking and Finance (GPA 5.4/6.0)   09/2022 - 06/2024
- Exchange semester at Bocconi, Milan
- Thesis on covenant pricing in mid-market lending
""", 2),

    ("German: institution above, degree beneath", """Ausbildung
Universität St. Gallen, St. Gallen                    09/2022 - 06/2024
Master of Arts in Banking and Finance
- Notendurchschnitt 5.4 / 6.0
- Masterarbeit über Covenant-Pricing im Mittelstandskredit
""", 2),

    ("Matura entry beneath a degree, year only", """Education
MA in Banking and Finance, University of St. Gallen   09/2022 - 06/2024
- Grade average 5.4 / 6.0
Kantonsschule Wettingen                               2015 - 2019
- Matura, focus on economics and law
""", 2),

    ("education and certificates under one heading", """Education & Certificates
MA in Banking and Finance, University of St. Gallen   09/2022 - 06/2024
- Grade average 5.4 / 6.0
Bloomberg Market Concepts                             03/2023
- Twelve-hour e-learning introduction to the financial markets
""", 2),
]

EDUCATION = """
Education
MA in Banking and Finance, University of St. Gallen   09/2019 - 06/2021
- Major in Corporate Finance
"""


# --- leaks: a repair meant for one layout firing on another -----------------
#
# Every fix above is a rule that says "when the text looks like THIS, read it
# like THAT". Each one can misfire on a layout it was not meant for, and a
# misfire is silent. So each rule gets a case where it must NOT fire, with the
# finding that proves it did not.
#
# (name, section, issue keys that must NOT appear, issue keys that MUST appear)
LEAKS = [
    # join_split_ranges rejoins a range a table split across two lines. It must
    # not weld together two bare years that belong to different entries.
    ("two bare years from different entries are not welded into a range", """Education
Universitaet Zuerich, BA Economics
2019
Kantonsschule Wettingen
2015
Work Experience
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
- Rebuilt the monthly reporting pack, cutting two days off the close
""", ["date_overlap", "date_gap"], []),

    ("a genuine overlap is still reported", """Work Experience
Analyst, Beispiel AG, Zurich                          09/2021 - 06/2023
- Built the quarterly reporting pack
Consultant, Andere AG, Basel                          01/2022 - 09/2024
- Advised two clients on cost reduction
""", [], ["date_overlap"]),

    ("an entry with genuinely no role title is still caught", """Work Experience
Beispiel AG                                           09/2022 - 08/2024
- Rebuilt the monthly reporting pack, cutting two days off the close
Andere AG                                             01/2020 - 08/2022
- Ran reconciliations across four entities
""", [], ["entries_no_title"]),

    ("an entry with genuinely no description is still caught", """Work Experience
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024

Consultant, Andere AG, Basel                          01/2020 - 08/2022

Intern, Dritte AG, Bern                               06/2019 - 12/2019
""", [], ["entries_no_detail"]),

    ("a wrapped title line is not read as a bullet", """Work Experience
Analyst, Corporate Finance and Capital Markets Advisory,
    Beispiel Aktiengesellschaft, Zurich               09/2022 - 08/2024
- Rebuilt the monthly reporting pack, cutting two days off the close
- Ran reconciliations across four entities
""", ["no_bullets_anywhere"], []),

    # The indented-line rule must not invent bullets where there are none.
    ("a CV with truly no bullets is still caught", """Work Experience
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
Consultant, Andere AG, Basel                          01/2020 - 08/2022
Education
MA in Banking and Finance, University of St. Gallen   09/2019 - 06/2021
""", [], ["no_bullets_anywhere"]),
]


EXPERIENCE_TAIL = """
Work Experience
Analyst, Beispiel AG, Zurich                          09/2024 - 08/2025
- Rebuilt the monthly reporting pack, cutting two days off the close
"""


def check(name: str, section: str, bullets: int,
          category: str = "Experience", tail: str = None) -> list[str]:
    text = section + (EDUCATION if tail is None else tail)
    sections = section_coverage.detect_sections(text)
    facts = cv_facts.analyse(text, {"page_count": 1}, sections)
    issues = {i["key"] for i in severity.assess(facts)["all_issues"]}
    experience = next((s for s in facts["sections"]
                       if s["category"] == category), None)

    problems = []
    if experience is None:
        return ["the experience section was not found at all"]
    if not experience["entry_count"]:
        problems.append("no entries found")
    if experience["bullet_count"] < bullets:
        problems.append(f"{experience['bullet_count']} bullets found, expected {bullets}")
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
    for name, section, bullets in LAYOUTS:
        problems = check(name, section, bullets)
        if problems:
            failed += 1
            print(f"FAIL  {name}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"ok    {name}")
    print()
    for name, section, bullets in EDUCATION_LAYOUTS:
        problems = check(name, section, bullets, "Education", EXPERIENCE_TAIL)
        if problems:
            failed += 1
            print(f"FAIL  education: {name}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"ok    education: {name}")

    print()
    for name, section, forbidden, required in LEAKS:
        # Self-contained: a shared tail would supply bullets or dates of its own
        # and the case would stop testing what it says it tests.
        text = section if "Education" in section else section + EDUCATION
        sections = section_coverage.detect_sections(text)
        facts = cv_facts.analyse(text, {"page_count": 1}, sections)
        keys = {i["key"] for i in severity.assess(facts)["all_issues"]}
        problems = [f"{k!r} leaked in" for k in forbidden if k in keys]
        problems += [f"{k!r} was missed" for k in required if k not in keys]
        if problems:
            failed += 1
            print(f"FAIL  leak: {name}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"ok    leak: {name}")

    # A heading is a category label, not a name. The keyword fallback that lets
    # "Academic Experience" be read as education must not promote a club or an
    # employer to a section, and the qualifier must beat the generic noun:
    # "Academic Experience" is education, not experience.
    print()
    from guardrails import headings as _h
    HEADINGS = [
        ("Academic Experience", "Education"),
        ("Academic Qualifications", "Education"),
        ("Volunteering Experience", "Volunteering & Community"),
        ("Extracurricular Experience", "Extracurricular & Interests"),
        ("Leadership & Societies", "Extracurricular & Interests"),
        ("Research Experience", "Publications & Research"),
        ("Professional Experience", "Experience"),
        ("Praktische Berufserfahrung", "Experience"),
        ("Weitere Qualifikationen", "Certifications & Training"),
        ("Relevant Coursework", "Certifications & Training"),
        ("Radsport-Club Wettingen", None),
        ("Consulting Club HSG", None),
        ("Impulse Network, Switzerland", None),
        ("Kantonsschule Wettingen", None),
        ("University of St. Gallen (HSG)", None),
        ("12-wöchige Grundausbildung", None),
        ("online presence and social media", None),
        ("My Journey", None),
    ]
    wrong = []
    for heading, expected in HEADINGS:
        entry = _h.identify(heading)
        got = entry["category"] if entry else None
        if got != expected:
            wrong.append(f"{heading!r} -> {got}, expected {expected}")
    if wrong:
        failed += 1
        print("FAIL  headings: category label vs name")
        for line in wrong:
            print(f"        {line}")
    else:
        print(f"ok    headings: {len(HEADINGS)} category-vs-name cases")

    total = len(LAYOUTS) + len(EDUCATION_LAYOUTS) + len(LEAKS) + 1
    print(f"\n{total - failed}/{total} layouts read correctly")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
