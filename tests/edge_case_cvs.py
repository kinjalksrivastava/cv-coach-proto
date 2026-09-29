"""
CVs built to break the parser, and what the parser is supposed to make of them.

Every case here comes from something a reviewer actually sent back, or from a
failure found while fixing one of those. They run offline - no model call, no
network - so this is the check to run before a push, and the place to add a case
the moment a new parsing complaint arrives.

    ./venv/bin/python tests/edge_case_cvs.py

Each case states what must be TRUE of the parse. The assertions are deliberately
about facts, not wording: what got found, what did not, and what must not be
reported as a problem when it isn't one.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv_facts  # noqa: E402
import severity  # noqa: E402
import format_check  # noqa: E402
from guardrails import headings as heading_lookup  # noqa: E402
from guardrails import section_coverage  # noqa: E402

# An icon font maps into the Unicode private use area. This is what one looks
# like once it has been through a PDF text extractor.
ICON = ""

CASES: list[dict] = []


def case(name, text, meta=None, **checks):
    CASES.append({"name": name, "text": text, "meta": meta or {"page_count": 1},
                  "checks": checks})


# --------------------------------------------------------------------------
# 1. German CV with icons beside every heading.
#    MP: "It says that «Berufserfahrung» may not be recognised even though this
#    is the most common section title and I selected German during the upload."
#    Serena: "This CV actually has Icons before each section header and I think
#    it picks these up as letters when parsed."
# --------------------------------------------------------------------------
case(
    "german_cv_with_icons",
    f"""{ICON} BERUFSERFAHRUNG
Praktikant Controlling, Beispiel AG, Zürich          09/2023 - 03/2024
- Aufbereitung des monatlichen Reportings für die Geschäftsleitung
- Durchführung von Abstimmungen im Hauptbuch

S AUSBILDUNG
BA Betriebswirtschaftslehre, Universität St. Gallen  09/2021 - 06/2024
- Schwerpunkt Finanzen und Rechnungswesen

{ICON} SPRACHEN
Deutsch: Muttersprache
Englisch: C1
""",
    headings=["BERUFSERFAHRUNG", "AUSBILDUNG", "SPRACHEN"],
    categories=["Experience", "Education", "Skills & Languages"],
    # One icon survived as the letter "S"; the other two were private-use
    # codepoints, stripped during extraction and reported from there.
    icon_damage=1,
    icon_lines=2,
    # The whole point: a correct German heading must never be reported as one an
    # ATS may not recognise. Naming it as icon-damaged is fine and wanted.
    ats_must_not_flag_headings=True,
    no_issue_kinds=["no_bullets_anywhere", "entries_no_detail"],
)

# --------------------------------------------------------------------------
# 2. Two roles under one employer, stacked after a promotion. This is the layout
#    Career Services themselves recommend.
#    Serena: "This person had two roles under one employer... It should pick
#    this up properly."
# --------------------------------------------------------------------------
case(
    "stacked_roles_one_employer",
    """Work Experience
UBS AG, Zurich
Senior Analyst                                      09/2023 - present
Analyst                                             09/2021 - 08/2023
- Rebuilt the quarterly reporting pack, cutting three days off the close
- Ran reconciliations across four entities

Education
MA in Banking and Finance, University of St. Gallen  09/2019 - 06/2021
""",
    headings=["Work Experience", "Education"],
    # The first role owns no bullets because the second starts on the next line.
    # Reporting it as an entry with no description is an invented tier-1 finding.
    no_issue_kinds=["entries_no_detail", "no_bullets_anywhere"],
)

# --------------------------------------------------------------------------
# 3. Education entries have no "role", which is correct and must not be flagged.
#    MP: "In the education section there shouldn't be a 'role'. Only in
#    professional experience and extracurricular experience."
# --------------------------------------------------------------------------
case(
    "education_needs_no_role_title",
    """Education
University of St. Gallen                            09/2021 - 06/2024
- BA in Business Administration, major in Finance

Gymnasium Zurich                                    08/2017 - 06/2021
- Matura, focus on economics and law

Work Experience
Intern, Credit Suisse, Zurich                       07/2023 - 09/2023
- Supported the equity research team with sector screens
""",
    no_issue_kinds=["entries_no_title"],
)

# --------------------------------------------------------------------------
# 4. A profile at the top with no heading over it.
#    Serena: "This person also has a personal profile at the top, which does not
#    seem to be picked up here. Maybe because the header is missing for it."
# --------------------------------------------------------------------------
case(
    "profile_without_a_heading",
    """Final-year business student with a focus on sustainable finance, looking for a
graduate role in ESG research. Comfortable working across German and English and
with three internships behind me in reporting and analysis.

Education
BA in Business Administration, HSG                  09/2021 - 06/2024
- Major in Finance

Work Experience
Intern, ESG Research, Zurich                        06/2023 - 09/2023
- Screened 40 portfolio companies against the SFDR criteria
""",
    issue_kinds=["unlabelled_intro"],
)

# --------------------------------------------------------------------------
# 5. Years with no months anywhere.
#    MP: "It doesn't tell the person to add months (instead of only years)."
#    It must also NOT invent overlaps out of year-only boundaries: finishing a
#    degree in 2021 and starting a job in 2021 is not two things at once.
# --------------------------------------------------------------------------
case(
    "years_without_months",
    """Education
BA in Economics, University of Zurich               2017 - 2021
- Thesis on Swiss housing policy

Work Experience
Analyst, Some Bank, Zurich                          2021 - 2023
- Built the monthly management reporting pack
Intern, Another Firm, Basel                         2023 - 2024
- Supported the corporate finance team on two mandates
""",
    issue_kinds=["year_only_dates"],
    no_issue_kinds=["overlap"],
)

# --------------------------------------------------------------------------
# 6. Heading typos, and dates mangled by the scanner.
#    MP: "Educatiqn instead of Education (even though the student wrote it
#    correctly in the CV)" - the heading must still be understood as Education.
# --------------------------------------------------------------------------
case(
    "typo_headings_and_dates",
    """Educatiqn
BA in Business Administration, HSG                  Sep 2021 - 3un 2025
- Major in Finance

Work Experience
Intern, Some Firm, Zurich                           Feb,2022-Nov,2022
- Prepared the weekly sales report for the regional team
""",
    categories=["Education", "Experience"],
    issue_kinds=["typos"],
)

# --------------------------------------------------------------------------
# 7. Every date format seen in a real upload, in one document. None of them may
#    be missed, and none of them may produce a phantom gap or overlap.
# --------------------------------------------------------------------------
case(
    "every_date_format",
    """Work Experience
Werkstudent, Firma A, München                       10.2021 – Heute
- Betreuung des monatlichen Reportings
Praktikant, Firma B, Berlin                         Dez 2020 - Mai 2021
- Unterstützung im Controlling
Intern, Firm C, London                              09/2019 – 06/2020
- Ran the weekly pipeline review
Assistant, Firm D, Zurich                           September 2018 - April 2019
- Prepared board papers for the quarterly meeting
""",
    date_ranges=4,
    no_issue_kinds=["overlap"],
)

# --------------------------------------------------------------------------
# 8. A CV with genuinely nothing on it. Every tier-1 check should fire, and the
#    report must not run out of things to say.
#    Serena: "There are lots of improvements this person could make - why are
#    there only two things listed?"
# --------------------------------------------------------------------------
case(
    "almost_empty_cv",
    """Education
University of St. Gallen                            2021 - 2024

Work Experience
Some Company                                        2023 - 2024

Skills
Microsoft Office
""",
    issue_kinds=["entries_no_detail"],
    min_issues=3,
)

# --------------------------------------------------------------------------
# 9. A good CV. The most important case in the file: nothing must be invented.
# --------------------------------------------------------------------------
case(
    "clean_cv_invents_nothing",
    """Profile
Business student specialising in corporate finance, seeking a summer analyst role.

Education
MA in Banking and Finance, University of St. Gallen  09/2022 - 06/2024
- Grade average 5.4 / 6.0, major in Corporate Finance
- Exchange semester at Bocconi, Milan

Work Experience
Summer Analyst, Zurich Kantonalbank, Zurich          06/2023 - 08/2023
- Built the DCF model behind a CHF 40m mid-market acquisition
- Presented the sector screen to the deal team, shaping the final shortlist

Extracurricular Experience
Treasurer, Consulting Club HSG                       09/2022 - 06/2023
- Rebuilt the budget process, cutting month-end close from five days to two

Languages and IT Skills
German: Native
English: C1
Excel, Python, Bloomberg

Interests
Climbing (multi-pitch routes, Piz Bernina), classical guitar (10 years)
""",
    headings=["Profile", "Education", "Work Experience", "Extracurricular Experience",
              "Languages and IT Skills", "Interests"],
    no_issue_kinds=["no_bullets_anywhere", "entries_no_detail", "entries_no_title",
                    "unlabelled_intro", "no_outcomes", "duty_bullets"],
    missing_report_sections=["Courses and Certificates (optional)"],
)


def run() -> int:
    failures = 0
    for item in CASES:
        checks = item["checks"]
        # Mirror the real pipeline: extraction strips icon codepoints first and
        # records the lines they were on.
        text, icon_lines = heading_lookup.strip_private_use(item["text"])
        meta = {**item["meta"], "icon_lines": icon_lines}
        sections = section_coverage.detect_sections(text)   # offline, no model
        facts = cv_facts.analyse(text, meta, sections)
        result = severity.assess(facts)
        kinds = {i["key"] for i in result["all_issues"]}
        rows = format_check.run(text, meta, facts)
        problems = []

        if "headings" in checks:
            got = [s["heading"] for s in sections]
            if got != checks["headings"]:
                problems.append(f"headings {got} != {checks['headings']}")
        if "categories" in checks:
            got = [s["category"] for s in sections]
            if got != checks["categories"]:
                problems.append(f"categories {got} != {checks['categories']}")
        if "icon_damage" in checks:
            got = sum(1 for s in sections if s.get("damage") == "icon")
            if got != checks["icon_damage"]:
                problems.append(f"icon damage {got} != {checks['icon_damage']}")
        for kind in checks.get("issue_kinds", []):
            if kind not in kinds:
                problems.append(f"missing issue '{kind}' (got {sorted(kinds)})")
        for kind in checks.get("no_issue_kinds", []):
            if kind in kinds:
                problems.append(f"invented issue '{kind}'")
        if "min_issues" in checks and len(result["all_issues"]) < checks["min_issues"]:
            problems.append(f"only {len(result['all_issues'])} issues, "
                            f"expected >= {checks['min_issues']}")
        if "date_ranges" in checks:
            from guardrails import dates
            got = len(dates.extract_ranges(text))
            if got != checks["date_ranges"]:
                problems.append(f"{got} date ranges != {checks['date_ranges']}")
        if "missing_report_sections" in checks:
            got = facts["missing_report_sections"]
            if got != checks["missing_report_sections"]:
                problems.append(f"missing sections {got} != "
                                f"{checks['missing_report_sections']}")
        if "icon_lines" in checks and len(icon_lines) != checks["icon_lines"]:
            problems.append(f"{len(icon_lines)} icon lines != {checks['icon_lines']}")
        ats = next((r["comment"] for r in rows if "ATS" in r["check"]), "")
        if checks.get("ats_must_not_flag_headings") and "may not recognise" in ats:
            problems.append(f"ATS row calls a correct heading unrecognisable: {ats}")

        if problems:
            failures += 1
            print(f"FAIL  {item['name']}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"ok    {item['name']}")

    # The production path when the student gives no job description passes None,
    # not "". The cases above all default to "", so nothing here covered it, and
    # `None.strip()` took the deployed app down on the first upload without a JD.
    try:
        case = CASES[-1]
        text, _ = heading_lookup.strip_private_use(case["text"])
        sections = section_coverage.detect_sections(text)
        facts = cv_facts.analyse(text, case["meta"], sections, None)
        severity.assess(facts)
        assert facts["jd_provided"] is False
        print("ok    no_job_description_is_none")
    except Exception as exc:
        failures += 1
        print(f"FAIL  no_job_description_is_none\n        {exc!r}")

    print(f"\n{len(CASES) + 1 - failures}/{len(CASES) + 1} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
