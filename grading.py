"""
Grades: which scale a number is on, whether it can be real, and what is missing.

Career Services' feedback was specific here. A CV that says "Grade Average: 513"
should be challenged rather than repeated back; a grade should always carry its
maximum ("5.13 / 6.00") so a recruiter in another country can read it; and if one
degree shows a grade, the others should too, because an omission reads as a bad
result.

What this module deliberately does NOT do is judge a grade. There is no "below
5.0 is weak" rule here: a scale tells you whether a number is possible, not
whether it is good, and calling a grade weak is exactly the scoring the whole
product refuses to do. The only judgements made are "this number cannot exist on
any scale we know" and "this number has no maximum next to it".

Everything is local and deterministic - the model is told what was found, it does
not go looking itself.
"""

import re

# Scale definitions per country. `best_is_low` matters because a German 1.3 is
# excellent and a Swiss 1.3 is a fail - without it, "plausible" is meaningless.
SCALES = {
    "CH": {"name": "Swiss (1-6)", "lo": 1.0, "hi": 6.0, "best_is_low": False, "pass": 4.0},
    "DE": {"name": "German (1.0-5.0, 1 is best)", "lo": 1.0, "hi": 5.0, "best_is_low": True},
    "AT": {"name": "Austrian (1-5, 1 is best)", "lo": 1.0, "hi": 5.0, "best_is_low": True},
    "IT": {"name": "Italian (18-30 per exam, 66-110 degree)", "lo": 18.0, "hi": 110.0, "best_is_low": False},
    "FR": {"name": "French (0-20)", "lo": 0.0, "hi": 20.0, "best_is_low": False},
    "UK": {"name": "UK percentage (0-100)", "lo": 0.0, "hi": 100.0, "best_is_low": False},
    "US": {"name": "US GPA (0-4.0)", "lo": 0.0, "hi": 4.0, "best_is_low": False},
    "IN": {"name": "Indian CGPA (0-10)", "lo": 0.0, "hi": 10.0, "best_is_low": False},
    "NL": {"name": "Dutch (1-10)", "lo": 1.0, "hi": 10.0, "best_is_low": False},
}

# The German Abitur is its own thing and students write it both ways.
ABITUR_AVERAGE = {"name": "Abitur average (1.0-4.0, 1 is best)", "lo": 1.0, "hi": 4.0, "best_is_low": True}
ABITUR_POINTS = {"name": "Abitur points (0-900)", "lo": 0.0, "hi": 900.0, "best_is_low": False}

# Place names that appear on HSG students' CVs, mapped to the grading system in
# force there. Only used as a hint: a wrong guess downgrades to "unknown scale",
# it never produces a confident claim.
PLACE_COUNTRY = {
    "CH": ["st. gallen", "st.gallen", "sankt gallen", "zurich", "zürich", "basel", "bern",
           "lausanne", "geneva", "genf", "lugano", "switzerland", "schweiz", " ch"],
    "DE": ["germany", "deutschland", "berlin", "munich", "münchen", "hamburg", "frankfurt",
           "cologne", "köln", "karlsruhe", "stuttgart", "mannheim", "heidelberg", "abitur"],
    "AT": ["austria", "österreich", "vienna", "wien", "graz", "salzburg"],
    "IT": ["italy", "italia", "milan", "milano", "rome", "roma", "bocconi", "bologna"],
    "FR": ["france", "paris", "lyon", "hec", "essec", "sciences po"],
    "UK": ["united kingdom", "england", "london", "oxford", "cambridge", "warwick",
           "manchester", "lse", " uk"],
    "US": ["united states", "usa", " us,", "new york", "boston", "chicago", "california"],
    "IN": ["india", "delhi", "mumbai", "chennai", "bangalore", "bengaluru"],
    "NL": ["netherlands", "amsterdam", "rotterdam", "maastricht", "erasmus"],
}

GRADE_KEYWORDS = re.compile(
    r"\b(grade|grades|grade average|gpa|cgpa|note|notendurchschnitt|durchschnitt|"
    r"abitur|matura|final grade|overall grade|classification|graded|mark|marks)\b",
    re.IGNORECASE,
)

# A number that could be a grade: 1-3 digits, optional decimal, optionally with
# its maximum after a slash. The lookarounds keep it from biting a chunk out of a
# longer number - without them "Jun 2022" yields a "202", which is how an early
# version of this module invented two grades that were never on the CV.
GRADE_NUMBER = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:/\s*(\d{1,3}(?:[.,]\d{1,2})?))?(?![\d])"
)

# Date ranges are stripped before grades are looked for, for the same reason.
DATE_RANGE_IN_LINE = re.compile(
    r"((?:[A-Za-zäöü]{3,9}\.?,?\s*)?(?:19|20)\d{2})\s*[-–—]\s*"
    r"((?:[A-Za-zäöü]{3,9}\.?,?\s*)?(?:19|20)\d{2}|present|current|heute|now)",
    re.IGNORECASE,
)
BARE_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def _to_float(token: str) -> float:
    return float(token.replace(",", "."))


def country_for(line: str, context: str = "") -> str | None:
    """
    Which country's scale applies to this entry. The entry's OWN line wins: an
    Abitur from Karlsruhe is on the German scale even though the CV mentions
    St. Gallen three lines further down. Context is only a fallback.
    """
    for haystack in (line.lower(), context.lower()):
        for code, needles in PLACE_COUNTRY.items():
            if any(n in haystack for n in needles):
                return code
    return None


def _candidate_scales(country: str | None, line: str) -> list[dict]:
    lowered = line.lower()
    if "abitur" in lowered:
        return [ABITUR_AVERAGE, ABITUR_POINTS]
    if country and country in SCALES:
        return [SCALES[country]]
    return list(SCALES.values())


def _plausible_on(value: float, scale: dict) -> bool:
    return scale["lo"] <= value <= scale["hi"]


def _repair(value: float, scales: list[dict]) -> float | None:
    """
    "513" on a Swiss CV is almost certainly 5.13 with the decimal point lost in
    the scan. Try shifting the decimal left and see whether the result becomes
    possible; only suggest it when exactly one shift works.
    """
    hits = []
    for shift in (10.0, 100.0):
        shifted = value / shift
        if any(_plausible_on(shifted, s) for s in scales):
            hits.append(round(shifted, 2))
    return hits[0] if len(hits) == 1 else None


def find_grades(text: str, section_lines: list[str] | None = None) -> list[dict]:
    """
    Every grade mention in the text, with what we can say about it.

    Each result: {raw, value, maximum, line, country, scale, plausible,
                  suggestion, missing_maximum}
    """
    context = "\n".join(section_lines) if section_lines else text
    found = []
    for line in text.splitlines():
        if not GRADE_KEYWORDS.search(line):
            continue
        # Strip dates and years before looking for numbers. An entry line like
        # "Sep 2013 - Jun 2022 Bismarck Gymnasium Karlsruhe - Abitur" matches the
        # grade keyword, and scanning it raw yields "201" and "202" sliced out of
        # the years - two grades that were never on the CV.
        scannable = BARE_YEAR.sub(" ", DATE_RANGE_IN_LINE.sub(" ", line))
        for match in GRADE_NUMBER.finditer(scannable):
            token, max_token = match.group(1), match.group(2)
            value = _to_float(token)
            country = country_for(line, context)
            scales = _candidate_scales(country, line)
            plausible = any(_plausible_on(value, s) for s in scales)
            scale_name = next((s["name"] for s in scales if _plausible_on(value, s)), None)
            found.append({
                "raw": match.group(0).strip(),
                "value": value,
                "maximum": _to_float(max_token) if max_token else None,
                "line": line.strip(),
                "country": country,
                "scale": scale_name,
                "plausible": plausible,
                "suggestion": None if plausible else _repair(value, scales),
                "missing_maximum": max_token is None,
            })
    return found


def describe(grades: list[dict]) -> list[str]:
    """Plain statements of fact for the report prompt - never a judgement."""
    notes = []
    for g in grades:
        where = f'on the line "{g["line"][:70]}"'
        if not g["plausible"]:
            if g["suggestion"] is not None:
                info = SCALES.get(g["country"], {})
                scale = info.get("name", "the local scale")
                top = info.get("hi")
                # Knowing the country means knowing the maximum, so state it
                # rather than asking the student what it is.
                if top:
                    notes.append(
                        f'The grade "{g["raw"]}" {where} is not a possible value on '
                        f'{scale}. It is almost certainly {g["suggestion"]} with the '
                        f'decimal point lost. Confirm this with the student and tell them '
                        f'to write it as {g["suggestion"]} / {top:.2f} - the maximum must '
                        f'be on the CV so a reader in another country can read it.'
                    )
                else:
                    notes.append(
                        f'The grade "{g["raw"]}" {where} is not a possible value on '
                        f'{scale}. It may be {g["suggestion"]}. Ask the student to confirm '
                        f'and to write it with its maximum.'
                    )
            else:
                notes.append(
                    f'The grade "{g["raw"]}" {where} does not match any grading scale '
                    f"this tool recognises. Ask the student which scale it is on."
                )
        elif g["missing_maximum"]:
            top = SCALES.get(g["country"], {}).get("hi")
            target = f'{g["value"]:g} / {top:.2f}' if top else "a value out of its maximum"
            notes.append(
                f'The grade "{g["raw"]}" {where} is given without its maximum. '
                f'A recruiter in another country cannot read it - it should be written '
                f'as {target}.'
            )
    return notes


def consistency_note(education_entry_count: int, entries_with_grades: int) -> str | None:
    """
    Career Services' rule: showing a grade for one degree and not another invites
    the reader to assume the missing one was poor. Stated as the convention it is,
    with no claim about the student's actual results.
    """
    if education_entry_count >= 2 and 0 < entries_with_grades < education_entry_count:
        return (
            f"{entries_with_grades} of {education_entry_count} education entries show a "
            "grade, the rest do not. Grades are optional throughout, but showing some and "
            "hiding others is the one option that works against the student."
        )
    return None
