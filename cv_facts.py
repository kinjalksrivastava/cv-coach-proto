"""
What is measurably true about this CV, computed in code before any model sees it.

This module exists because of one specific failure. Asked to describe the CV, the
model said "includes Abitur grade average" when the grade actually sat under the
St. Gallen entry, and "experience bullets lack detail" when that section had no
bullets at all. Both were confabulations produced by a model reading extracted
text and filling gaps. Career Services' response was unambiguous: the report must
not be factually wrong about the document.

So the division of labour is now: this module decides WHAT IS TRUE, severity.py
decides WHAT MATTERS, and the model only decides HOW TO SAY IT. The model is
handed these facts and told not to assert anything outside them.

Everything here is deterministic and local. Where a check cannot be made
reliably it is left out rather than guessed - a shaky finding is worse than a
missing one, because a false finding is exactly what the reviewers objected to.
"""

import re
from difflib import SequenceMatcher

# A line that STARTS with one of these is a bullet - "- Did benchmark research".
BULLET_CHARS = "-–—•·*▪◦‣"
BULLET_LINE = re.compile(rf"^\s*[{re.escape(BULLET_CHARS)}]\s+\S")

# Mid-line, only true bullet glyphs count. A spaced hyphen is a date or title
# separator far more often than a bullet ("Sep 2024 - Jun 2025 St Gallen
# Symposium"), and counting those entry lines as bullets made every section
# report zero entries - while reporting the job lines themselves as bullets.
INLINE_BULLET_CHARS = "•·▪◦‣"
INLINE_BULLET = re.compile(rf"\s[{re.escape(INLINE_BULLET_CHARS)}]\s+\S")

# One date parser for the whole project - see guardrails/dates.py. Keeping a
# second copy here is how "2019 - 2021" ended up invisible to the gap check
# while cv_facts still saw it.
from guardrails.dates import RANGE_RE as DATE_RANGE

MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
          "januar", "februar", "märz", "april", "mai", "juni", "juli", "august",
          "september", "oktober", "november", "dezember", "sept")

# Openers that describe a duty rather than a contribution. Career Services'
# tier 2. Kept to an explicit list: inferring "weak phrasing" more generally
# produces exactly the invented findings the reviewers complained about.
WEAK_OPENERS = (
    "responsible for", "was responsible", "duties included", "tasks included",
    "helped with", "helped to", "assisted with", "assisted in", "assisted the",
    "involved in", "was involved", "participated in", "took part in",
    "worked on", "worked with", "supported the", "in charge of",
    "zuständig für", "verantwortlich für", "mitgewirkt", "unterstützte",
)

# Claims that assert a trait with nothing behind it. Career Services' tier 5.
BUZZWORDS = (
    "hardworking", "hard-working", "team player", "motivated", "self-motivated",
    "detail-oriented", "detail oriented", "results-oriented", "goal-oriented",
    "adaptability", "adaptable", "self-initiative", "high self-initiative",
    "analytic thinking", "analytical thinking", "fast learner",
    "quick learner", "proactive", "dynamic", "passionate", "flexible",
    "teamfähig", "belastbar", "zuverlässig", "engagiert",
)

# British / American pairs that appear on CVs. Both present in one document is a
# consistency problem worth mentioning; neither spelling is wrong on its own.
SPELLING_PAIRS = [
    ("organise", "organize"), ("organised", "organized"), ("analyse", "analyze"),
    ("analysed", "analyzed"), ("optimise", "optimize"), ("optimised", "optimized"),
    ("specialise", "specialize"), ("specialised", "specialized"),
    ("programme", "program"), ("centre", "center"), ("licence", "license"),
    ("behaviour", "behavior"), ("colour", "color"), ("favour", "favor"),
    ("labour", "labor"), ("defence", "defense"), ("catalogue", "catalog"),
    ("modelling", "modeling"), ("travelling", "traveling"), ("fulfil", "fulfill"),
    ("enrolment", "enrollment"), ("judgement", "judgment"),
]

# Headings a near-miss is measured against, for typo detection.
KNOWN_HEADINGS = (
    "education", "work experience", "professional experience", "experience",
    "employment", "skills", "technical skills", "it skills", "languages",
    "extracurricular activities", "extracurricular", "interests", "hobbies",
    "certificates", "certifications", "courses", "publications", "projects",
    "awards", "references", "profile", "summary", "volunteering",
    "core competences", "core competencies", "additional information",
    "community experience", "ausbildung", "berufserfahrung", "kenntnisse",
    "sprachen", "interessen",
)

STANDARD_SECTION_CATEGORIES = {
    "Education": ("education",),
    "Experience": ("work experience", "professional experience"),
    "Skills & Languages": ("skills", "languages"),
}

# "Bare" only means something for sections built out of entries. A languages
# section with two lines is complete, not bare.
ENTRY_SECTIONS = {
    "Education", "Experience", "Volunteering & Community", "Projects",
    "Publications & Research", "Extracurricular & Interests",
}

# Sections where an entry is expected to say what the student actually did.
# Education is not one of them: a degree line with a thesis description under it
# is complete, and demanding bullets there would invent a problem.
DETAIL_CATEGORIES = {"Experience", "Volunteering & Community", "Projects"}

# Lines that introduce interests rather than claim a competence.
INTEREST_LINE = re.compile(r"^\s*(hobbies|interests|freizeit|interessen)\b", re.IGNORECASE)

# Dates are only compared WITHIN a section. Comparing every range in the
# document flagged a degree overlapping an internship - which is what studying
# and interning looks like, not a defect - and produced seven findings on a CV
# with no real timeline problem. Overlaps are narrower still: two concurrent
# club roles are normal, so only jobs are checked against each other.
DATE_GAP_CATEGORIES = {"Education", "Experience"}
DATE_OVERLAP_CATEGORIES = {"Experience"}

# A bullet that opens with a duty phrase but lands on a measured result is not a
# weak bullet. Without this, "Supported the launch ... reducing delivery times by
# 50%" gets flagged - the invented finding the reviewers objected to.
IMPACT_MARKER = re.compile(
    r"(\d+\s*%|\bby \d|\b\d[\d.,]*\s*(k|m|mn|bn|million|billion|chf|eur|usd|€|\$)"
    r"|\breduc|\bincreas|\bimprov|\bgrew\b|\bgrowth\b|\bsav(ed|ing)|\bresult(ing|ed)"
    r"|\bleading to\b|\bachiev|\bdeliver(ed|ing)\b|\bwinning\b|\bsecured\b)",
    re.IGNORECASE,
)


def _is_bullet(line: str) -> bool:
    # An entry carries its own dates, so a date-bearing line is never a bullet
    # whatever punctuation it happens to contain.
    if DATE_RANGE.search(line):
        return False
    return bool(BULLET_LINE.match(line)) or bool(INLINE_BULLET.search(line))


def _bullet_text(line: str) -> str:
    stripped = line.strip()
    return stripped.lstrip(BULLET_CHARS + " ").strip()


def _close_to_known_heading(heading: str) -> str | None:
    """
    "Educatiqn" is a typo, "Community Experience" is a real heading. Only an
    almost-exact match counts, so a legitimately unusual heading isn't corrected.
    """
    value = heading.strip().lower()
    if value in KNOWN_HEADINGS:
        return None
    for known in KNOWN_HEADINGS:
        if abs(len(value) - len(known)) <= 2 and SequenceMatcher(None, value, known).ratio() >= 0.85:
            return known
    return None


def _month_typos(text: str) -> list[str]:
    """
    Catches "3un 2025" and "Gun 2026" - a token sitting where a month belongs
    that is one character away from a real month name.
    """
    found = []
    for match in re.finditer(r"\b([A-Za-z0-9]{3,4})\.?\s+((?:19|20)\d{2})\b", text):
        token = match.group(1).lower()
        if token in MONTHS or token.isdigit():
            continue
        for month in MONTHS[:12]:
            if SequenceMatcher(None, token, month).ratio() >= 0.6 and len(token) == len(month):
                found.append(f'"{match.group(0)}" - did you mean "{month.capitalize()} {match.group(2)}"?')
                break
    return found


def _split_sections(text: str, sections: list[dict]) -> list[dict]:
    """Slice the document into its sections, using the parsed headings as anchors."""
    lines = text.splitlines()
    anchors = []
    for section in sections:
        heading = section["heading"].strip()
        for index, line in enumerate(lines):
            if line.strip() == heading and index not in [a[0] for a in anchors]:
                anchors.append((index, section))
                break
    anchors.sort(key=lambda a: a[0])

    out = []
    for position, (index, section) in enumerate(anchors):
        end = anchors[position + 1][0] if position + 1 < len(anchors) else len(lines)
        body = lines[index + 1:end]
        out.append({**section, "start": index, "end": end, "lines": body})
    return out


def _entries(body: list[str]) -> list[dict]:
    """
    An entry is one job, degree or activity. Anchored on a date range, which is
    what almost every CV entry carries and what a bullet almost never does.
    """
    entries = []
    for offset, line in enumerate(body):
        if _is_bullet(line) or not line.strip():
            continue
        if DATE_RANGE.search(line):
            # Many CVs put the employer and role on one line and the dates and
            # location on the next. Anchoring on the date line alone would read
            # "September 2021 - April 2024 St. Gallen, CH" as the whole entry and
            # then report a missing job title that is plainly there.
            title = ""
            for back in range(offset - 1, max(offset - 3, -1), -1):
                candidate = body[back].strip()
                if candidate and not _is_bullet(candidate) and not DATE_RANGE.search(candidate):
                    title = candidate
                    break
            entries.append({"line": line.strip(), "title_line": title,
                            "offset": offset, "bullets": [], "description": []})
    for entry in entries:
        for line in body[entry["offset"] + 1:]:
            if DATE_RANGE.search(line) and not _is_bullet(line):
                break
            if _is_bullet(line):
                entry["bullets"].append(_bullet_text(line))
            elif line.strip() and line.strip() != entry["title_line"]:
                entry["description"].append(line.strip())
    return entries


def _has_role_title(entry: dict) -> bool:
    """
    An entry needs a role as well as an employer. Reads the title line and the
    date line together, since either may carry it. Conservative on purpose:
    calling a real job title missing would be exactly the kind of factual error
    this module exists to prevent.
    """
    combined = f'{entry.get("title_line", "")} {entry["line"]}'
    without_dates = DATE_RANGE.sub("", combined).strip(" ,-–—|")
    parts = [p.strip() for p in re.split(r"[|,–—]|\s-\s", without_dates) if p.strip()]
    return len(parts) >= 2 and all(len(p) > 2 for p in parts[:2])


CEFR_TOKEN = re.compile(r"\b[ABC][12]\b")
PLAIN_LEVEL = re.compile(
    r"\b(native|fluent|advanced|intermediate|basic|proficient|beginner|conversational|"
    r"mother ?tongue|muttersprache|fliessend|verhandlungssicher|grundkenntnisse)\b",
    re.IGNORECASE,
)
NATIVE_LEVEL = re.compile(r"\b(native|mother ?tongue|muttersprache)\b", re.IGNORECASE)
LANGUAGE_LINE = re.compile(r"^\s*([A-Za-zÄÖÜäöü]{3,20})\s*[:\-–]\s*(\S.*)$")


def _language_levels(sliced: list[dict]) -> dict:
    """
    Where each language sits on the ladder Career Services asked for: no level at
    all, a plain self-assessed label, or CEFR. A native language is left out of
    both lists - it is never an area for improvement.
    """
    section, missing, plain_only = None, [], []
    for block in sliced:
        heading = block["heading"].lower()
        if block["category"] != "Skills & Languages" and "language" not in heading \
                and "sprach" not in heading:
            continue
        for line in block["lines"]:
            match = LANGUAGE_LINE.match(line.strip())
            if not match:
                continue
            name, value = match.group(1), match.group(2)
            if NATIVE_LEVEL.search(value):
                continue
            section = section or block["heading"]
            if CEFR_TOKEN.search(value):
                continue
            if PLAIN_LEVEL.search(value):
                plain_only.append(f"{name}: {value.strip()}")
            else:
                missing.append(f"{name}: {value.strip()}")
    return {"section": section, "missing": missing, "plain_only": plain_only}


def _single_word_interests(sliced: list[dict]) -> tuple[str | None, list[str]]:
    """
    "Chess", "Shogi" on their own tell a reader nothing. Career Services' rule is
    that a bare interest needs detail - what kind, how often, to what level.
    Only entries of one or two words count, so a described interest is left alone.
    """
    for section in sliced:
        if section["category"] != "Extracurricular & Interests":
            continue
        bare = []
        for line in section["lines"]:
            item = line.strip().strip("•-–—*· ").strip()
            if not item or any(ch.isdigit() for ch in item):
                continue
            words = item.replace(",", " ").split()
            if 1 <= len(words) <= 2 and len(item) <= 28:
                bare.append(item)
        if bare:
            return section["heading"], bare
    return None, []


# --- AI skills, and tailoring to the target role ---
#
# Career Services asked for both in their email of 21 September. Both are
# measured here rather than left to the model: "does this CV mention AI anywhere"
# and "how much of the job ad does this CV actually echo" are countable, and a
# model asked to judge them produces a different answer on every run.

AI_TERMS = re.compile(
    r"\b("
    r"a\.?i\.?|artificial intelligence|künstliche intelligenz|"
    r"machine learning|maschinelles lernen|deep learning|neural net\w*|"
    r"generative ai|gen ?ai|llm|large language model|sprachmodell|"
    r"chatgpt|gpt-?\d?|copilot|claude|gemini|midjourney|stable diffusion|"
    r"prompt engineering|nlp|natural language processing|computer vision|"
    r"tensorflow|pytorch|scikit-?learn|hugging ?face|langchain"
    r")\b",
    re.IGNORECASE,
)

# Words a job ad and a CV share regardless of the role, so matching on them would
# make every CV look tailored.
JD_NOISE = {
    "about", "above", "after", "also", "and", "any", "are", "around", "band", "been",
    "being", "both", "business", "candidate", "company", "count", "degree", "during",
    "each", "experience", "field", "first", "from", "full", "further", "good", "group",
    "have", "high", "into", "join", "knowledge", "level", "like", "look",
    "looking", "make", "more", "most", "must", "need", "offer", "only", "opportunity",
    "other", "our", "out", "over", "part", "please", "position", "profile", "role",
    "same", "skills", "some", "strong", "successful", "such", "support", "take", "team",
    "that", "their", "them", "there", "these", "they", "this", "through", "time",
    "under", "very", "well", "what", "when", "where", "which", "while", "will",
    "with", "within", "work", "working", "years", "your", "you",
    "und", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einer",
    "für", "mit", "von", "vom", "sind", "sich", "auch", "aber", "oder", "wir", "uns",
    "unser", "unsere", "dich", "deine", "deinem", "bei", "als", "auf", "aus", "nach",
    "nicht", "haben", "werden", "wird", "kannst", "sowie", "zum", "zur", "über",
    "erfahrung", "kenntnisse", "aufgaben", "stelle", "bereich", "team", "arbeiten",
}
_WORD = re.compile(r"[A-Za-zÄÖÜäöüß][\w&+#.-]{3,}")


def _jd_tailoring(cv_text: str, jd_text: str) -> dict:
    """
    How much of the job ad's own vocabulary the CV actually uses.

    Deliberately crude: it counts terms the ad repeats, then checks whether each
    appears anywhere in the CV. It cannot tell good tailoring from keyword
    stuffing - it only tells the model whether there is a tailoring gap worth
    raising, and names the terms so the feedback can be specific.
    """
    if not jd_text.strip():
        return {"jd_provided": False, "jd_terms_checked": 0,
                "jd_terms_missing": [], "jd_overlap": None}

    counts = {}
    for match in _WORD.finditer(jd_text.lower()):
        word = match.group(0).strip(".-")
        if len(word) < 4 or word in JD_NOISE or word.isdigit():
            continue
        counts[word] = counts.get(word, 0) + 1

    # Repeated terms are the ones the ad is actually about. If nothing repeats the
    # ad is too short to judge, and the check stays silent rather than guessing.
    repeated = sorted((w for w, n in counts.items() if n >= 2),
                      key=lambda w: -counts[w])[:25]
    if len(repeated) < 5:
        return {"jd_provided": True, "jd_terms_checked": 0,
                "jd_terms_missing": [], "jd_overlap": None}

    cv_lower = cv_text.lower()
    missing = [w for w in repeated if w[:5] not in cv_lower]
    return {
        "jd_provided": True,
        "jd_terms_checked": len(repeated),
        "jd_terms_missing": missing[:10],
        "jd_overlap": round((len(repeated) - len(missing)) / len(repeated), 2),
    }


def analyse(text: str, meta: dict, sections: list[dict], jd_text: str = "") -> dict:
    """
    Returns the facts. Every value is something measured, not inferred - the
    report prompt is told it may not assert anything this dict does not support.
    """
    import grading
    from guardrails import dates as date_check
    sliced = _split_sections(text, sections)

    # Every dated range in the document, used to tell a real gap from a period
    # the student was simply somewhere else on the CV.
    all_ranges = date_check.extract_ranges(text)

    def _covered_elsewhere(first_raw: str, second_raw: str, own: list[dict]) -> bool:
        """
        A gap between two internships is not a gap if the student was at
        university throughout - the Education section covers it. Without this,
        a strong CV came back with four "unexplained gap" findings that were
        just the spaces between internships during a full-time degree.
        """
        own_raws = {r["raw"] for r in own}
        starts = [r["end_idx"] for r in own if r["raw"] == first_raw]
        ends = [r["start_idx"] for r in own if r["raw"] == second_raw]
        if not starts or not ends:
            return False
        gap_start, gap_end = starts[0], ends[0]
        span = gap_end - gap_start
        if span <= 0:
            return False
        covered = 0
        for other in all_ranges:
            if other["raw"] in own_raws:
                continue
            overlap = min(gap_end, other["end_idx"]) - max(gap_start, other["start_idx"])
            covered = max(covered, max(0, overlap))
        return covered >= span * 0.6

    date_findings = []
    for section in sliced:
        if section["category"] not in DATE_GAP_CATEGORIES:
            continue
        body = "\n".join(section["lines"])
        own_ranges = date_check.extract_ranges(body)
        for finding in date_check.find_findings(body):
            if (finding["kind"] == "overlap"
                    and section["category"] not in DATE_OVERLAP_CATEGORIES):
                continue
            if finding["kind"] == "gap" and _covered_elsewhere(
                    finding["first"], finding["second"], own_ranges):
                continue
            finding["section"] = section["heading"]
            date_findings.append(finding)
    page_count = meta.get("page_count")
    char_count = meta.get("char_count") or len(text.strip())

    section_facts, all_bullets = [], []
    for section in sliced:
        body = section["lines"]
        bullets = [_bullet_text(line) for line in body if _is_bullet(line)]
        entries = _entries(body)
        all_bullets.extend(bullets)
        content = [line for line in body if line.strip()]
        section_facts.append({
            "heading": section["heading"],
            "category": section["category"],
            "line_count": len(content),
            "char_count": sum(len(line) for line in content),
            "bullet_count": len(bullets),
            "entry_count": len(entries),
            # "No detail" means no bullets AND no prose under the entry, and only
            # counts in sections where describing the work is the point.
            "entries_without_detail": [
                (e["title_line"] or e["line"]) for e in entries
                if section["category"] in DETAIL_CATEGORIES
                and not e["bullets"] and not e["description"]
            ],
            "entries_without_title": [
                (e["title_line"] or e["line"]) for e in entries if not _has_role_title(e)
            ],
            "heading_typo": _close_to_known_heading(section["heading"]),
            "is_bare": (len(content) <= 2 and not entries
                        and section["category"] in ENTRY_SECTIONS),
        })

    # Grades, and which education entries carry one.
    education = [s for s in sliced if s["category"] == "Education"]
    education_lines = [line for s in education for line in s["lines"]]
    grades = grading.find_grades("\n".join(education_lines) or text, education_lines)
    education_entries = [e for s in education for e in _entries(s["lines"])]
    entries_with_grade = sum(
        1 for e in education_entries
        if grading.GRADE_KEYWORDS.search(e["line"]) or any(
            grading.GRADE_KEYWORDS.search(b) for b in e["bullets"])
    )

    # Outcome density, measured only over sections where describing the work is
    # the point. A skills list is bullets too, and counting those would produce a
    # finding about "bullets with no outcome" on a CV whose only bullets are tools.
    # Tracked per section, not just as a flat list. Without the section a bullet
    # came from, the "weak bullets" issue carried no section, so the section it
    # described kept its Strong mark - which is the contradiction both reviewers
    # reported: key areas said the experience bullets were weak while section 5
    # called that same section Strong.
    detail_pairs = [
        (block["heading"], _bullet_text(line))
        for block in sliced if block["category"] in DETAIL_CATEGORIES
        for line in block["lines"] if _is_bullet(line)
    ]
    detail_bullets = [b for _, b in detail_pairs]
    with_outcome = [b for b in detail_bullets if IMPACT_MARKER.search(b)]
    no_outcome_pairs = [(h, b) for h, b in detail_pairs if not IMPACT_MARKER.search(b)]
    weak_pairs = [(h, b) for h, b in detail_pairs
                  if b.lower().startswith(WEAK_OPENERS) and not IMPACT_MARKER.search(b)]
    weak = [b for _, b in weak_pairs]

    def _dominant(pairs):
        counts = {}
        for heading, _ in pairs:
            counts[heading] = counts.get(heading, 0) + 1
        return max(counts, key=counts.get) if counts else None
    lowered = text.lower()
    # A trait word only counts where a trait is being CLAIMED as a skill. The
    # same word in an interests line ("passionate about soccer") is ordinary
    # prose, and flagging it would be a manufactured finding.
    claim_text = " ".join(
        line for s in sliced if s["category"] != "Extracurricular & Interests"
        for line in s["lines"] if not INTEREST_LINE.match(line)
    ).lower()
    buzz = sorted({w for w in BUZZWORDS if re.search(r"\b" + re.escape(w) + r"\b", claim_text)})
    mixed_spelling = [
        f"{uk}/{us}" for uk, us in SPELLING_PAIRS
        if re.search(rf"\b{uk}\w*", lowered) and re.search(rf"\b{us}\w*", lowered)
    ]

    # Bullet punctuation: only a finding when the split is genuinely mixed.
    ending = [b.endswith(".") for b in all_bullets if len(b) > 12]
    punctuation_mixed = len(ending) >= 4 and 0 < sum(ending) < len(ending)

    categories = [s["category"] for s in sliced]
    # A standard section counts as present if its CONTENT is there, whatever the
    # student called the heading. Languages listed under "Additional Information"
    # are still languages, and reporting them missing would be a false finding.
    missing_standard = [
        name for name, keywords in STANDARD_SECTION_CATEGORIES.items()
        if name not in categories
        and not any(re.search(r"\b" + re.escape(k) + r"\b", lowered) for k in keywords)
    ]

    return {
        "page_count": page_count,
        "char_count": char_count,
        "chars_per_page": round(char_count / page_count) if page_count else None,
        "fits_one_page": bool(page_count and page_count == 1),
        "too_long": bool(page_count and page_count > 2),
        "too_short": bool(page_count == 1 and char_count < 1200),
        "sections": section_facts,
        "total_bullets": len(all_bullets),
        "experience_bullets": len(detail_bullets),
        "experience_bullets_with_outcome": len(with_outcome),
        "bullets_without_outcome": [b for _, b in no_outcome_pairs][:5],
        "no_outcome_section": _dominant(no_outcome_pairs),
        "weak_opener_section": _dominant(weak_pairs),
        "has_no_bullets_anywhere": len(all_bullets) == 0,
        "weak_opener_bullets": weak[:6],
        "buzzwords": buzz,
        "mixed_spelling": mixed_spelling,
        "bullet_punctuation_mixed": punctuation_mixed,
        "heading_typos": [
            f'"{s["heading"]}" looks like a typo for "{s["heading_typo"]}"'
            for s in section_facts if s["heading_typo"]
        ],
        "month_typos": _month_typos(text),
        "date_findings": date_findings,
        # Career Services asked that a CV mentioning no AI skills anywhere - not in
        # coursework, not in a job, not under skills - be told so in the overall
        # impression. Measured across the whole document, since students put it in
        # whichever of those four places suits them.
        "mentions_ai": bool(AI_TERMS.search(text)),
        **_jd_tailoring(text, jd_text),
        "single_word_interests": _single_word_interests(sliced)[1],
        "single_word_interests_section": _single_word_interests(sliced)[0],
        "language_levels": _language_levels(sliced),
        "grades": grades,
        "grade_notes": grading.describe(grades),
        "grade_consistency": grading.consistency_note(len(education_entries), entries_with_grade),
        "missing_standard_sections": missing_standard,
        "table_count": meta.get("table_count", 0),
        "image_count": meta.get("image_count", 0),
        "section_order": [s["category"] for s in sliced],
        "education_after_experience": (
            "Education" in categories and "Experience" in categories
            and categories.index("Education") > categories.index("Experience")
        ),
    }


def describe_for_prompt(facts: dict) -> str:
    """The facts block handed to the report model as ground truth."""
    out = ["MEASURED FACTS ABOUT THIS CV (computed from the document itself - these are "
           "true; do not contradict them and do not assert anything beyond them):"]
    pages = facts["page_count"]
    out.append(f"- Pages: {pages if pages else 'not recoverable from this file type'}"
               f"; {facts['char_count']} characters of text.")
    out.append(f"- Bullet points in the whole CV: {facts['total_bullets']}.")
    for s in facts["sections"]:
        bits = [f'"{s["heading"]}" ({s["category"]})',
                f'{s["entry_count"]} entries', f'{s["bullet_count"]} bullets']
        if s["entries_without_detail"]:
            bits.append(f'{len(s["entries_without_detail"])} entries with NO bullets '
                        f'and no description at all')
        if s["entries_without_title"]:
            bits.append(f'{len(s["entries_without_title"])} entries with no clear role title')
        if s["is_bare"]:
            bits.append("section is bare")
        out.append("  - " + "; ".join(bits))
    if facts["grade_notes"]:
        out.append("- Grades: " + " ".join(facts["grade_notes"]))
    if facts["grade_consistency"]:
        out.append("- Grade consistency: " + facts["grade_consistency"])
    for key, label in (("heading_typos", "Likely heading typos"),
                       ("month_typos", "Likely date typos"),
                       ("mixed_spelling", "British/American spelling both used"),
                       ("buzzwords", "Unevidenced trait words"),
                       ("weak_opener_bullets", "Bullets opening with a duty phrase")):
        if facts.get(key):
            out.append(f"- {label}: " + "; ".join(str(x) for x in facts[key]))
    if facts["missing_standard_sections"]:
        out.append("- Standard sections not found: " + ", ".join(facts["missing_standard_sections"]))
    return "\n".join(out)
