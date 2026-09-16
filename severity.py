"""
What matters, and in what order.

Career Services supplied a five-tier ranking for "Key areas to improve" and asked
for the most damaging issues first, capped at five. This module turns the
measured facts into that ranked list.

Two review findings shaped the design:

  - The report used to produce exactly four improvement areas for every CV,
    because the prompt asked for "3-4 items". On a strong CV it invented some.
    Here the count is whatever the facts support - zero is a legitimate answer.

  - A key area said the experience bullets were weak while the same report
    marked that section "Strong". Statuses are now derived from the same issue
    list, so a section carrying an issue cannot come back green.

The model never decides WHAT is wrong. It receives this list and writes the
guidance prose for it.
"""

MAX_KEY_AREAS = 5

TIER_NAMES = {
    1: "No bullets or sparse content",
    2: "Weak bullet content",
    3: "Structure and consistency",
    4: "Missing sections or length",
    5: "Detail-level gaps",
}


def _issue(tier, key, title, evidence, section=None, guidance=""):
    return {"tier": tier, "key": key, "title": title, "evidence": evidence,
            "section": section, "guidance": guidance}


def strengths(facts: dict) -> list[str]:
    """
    Strengths, measured the same way problems are.

    Left to write these freely the model produced "the St. Gallen Symposium,
    which is well regarded" and "tools that are valued in business environments"
    - praise for the mere presence of a section, propped up by claims about what
    the market values that appear nowhere in the CV and were never measured.
    That is inventing, which is the one rule that cannot bend.

    So a strength here must be either a measured positive or a measured absence
    of a problem. Nothing about how impressive or valuable anything is.
    """
    found = []
    total = facts.get("experience_bullets", 0)
    with_outcome = facts.get("experience_bullets_with_outcome", 0)
    if total >= 4 and with_outcome / total >= 0.5:
        found.append(f"{with_outcome} of {total} experience bullets state a concrete "
                     f"result or figure rather than stopping at the task")

    for section in facts.get("sections", []):
        if (section["category"] in {"Experience", "Volunteering & Community", "Projects"}
                and section["entry_count"] >= 2
                and not section["entries_without_detail"]
                and not section["entries_without_title"]):
            found.append(f'every entry in "{section["heading"]}" carries both a role '
                         f"title and a description")

    if not (facts.get("heading_typos") or facts.get("month_typos")
            or facts.get("mixed_spelling")):
        found.append("headings, dates and spelling are consistent throughout")

    if facts.get("fits_one_page") and not facts.get("too_short"):
        found.append("it fits on one page without reading as thin")

    if not facts.get("date_findings"):
        found.append("the timeline runs without unexplained gaps or overlapping entries")

    grades = facts.get("grades") or []
    if grades and all(g["plausible"] and not g["missing_maximum"] for g in grades):
        found.append("grades are given with their maximum, so a reader in another "
                     "country can interpret them")

    if not facts.get("buzzwords"):
        found.append("skills are stated without unevidenced trait words")

    return found


def assess(facts: dict, target_role: str = "") -> dict:
    """
    Returns {"key_areas": [...at most five...], "all_issues": [...],
             "section_status": {heading: "strong"|"needs_attention"}}
    """
    issues: list[dict] = []
    date_findings = facts.get("date_findings", [])

    # Tier-5 findings need to know which section they belong to. Without it they
    # carry no section, the section keeps its "strong" mark, and the report ends
    # up telling a student to change something in a section it just called
    # strong - the same self-contradiction the reviewers flagged in section 4.
    def _section_named(*categories) -> str | None:
        for category in categories:
            for section in facts["sections"]:
                if section["category"] == category:
                    return section["heading"]
        return None

    education_section = _section_named("Education")
    skills_section = _section_named("Skills & Languages")
    role = target_role.strip()
    for_role = f" for {role}" if role else ""

    # --- Tier 1: there is nothing for a reader to evaluate --------------------
    if facts["has_no_bullets_anywhere"]:
        issues.append(_issue(
            1, "no_bullets_anywhere", "No bullet points anywhere in the CV",
            f"The document contains {facts['total_bullets']} bullet points in total.",
            guidance="Every role and activity needs a few lines saying what was actually "
                     "done. Without them a reader has only job titles to go on.",
        ))

    for section in facts["sections"]:
        if section["entries_without_detail"]:
            names = "; ".join(e[:60] for e in section["entries_without_detail"][:3])
            issues.append(_issue(
                1, "entries_no_detail",
                f'Entries in "{section["heading"]}" have no description',
                f'{len(section["entries_without_detail"])} of {section["entry_count"]} '
                f'entries have no bullets and no description: {names}',
                section=section["heading"],
                guidance="Add a few bullets under each one covering what was done, how, and "
                         f"what changed as a result — focused on the transferable skills "
                         f"that matter{for_role}.",
            ))
        if section["entries_without_title"]:
            issues.append(_issue(
                1, "entries_no_title",
                f'Entries in "{section["heading"]}" have no role title',
                f'{len(section["entries_without_title"])} entries name an organisation or '
                f'dates but no role: {"; ".join(e[:60] for e in section["entries_without_title"][:3])}',
                section=section["heading"],
                guidance="State the function you held alongside the organisation — a reader "
                         "cannot infer seniority or responsibility from an employer name.",
            ))
        if section["is_bare"]:
            issues.append(_issue(
                1, "bare_section", f'"{section["heading"]}" is almost empty',
                f'The section contains {section["line_count"]} lines of content.',
                section=section["heading"],
                guidance="Either develop this section or remove it — a heading with nothing "
                         "under it draws attention to the gap.",
            ))

    if facts["too_short"]:
        issues.append(_issue(
            1, "too_short", "The CV does not fill a page",
            f"About {facts['char_count']} characters of text on {facts['page_count']} page.",
            guidance="There is room to say considerably more about what you have done. "
                     "A student CV that stops halfway down page one reads as thin.",
        ))

    # --- Tier 2: bullets exist but do not communicate contribution ------------
    if facts["weak_opener_bullets"]:
        issues.append(_issue(
            2, "duty_bullets", "Bullets describe duties rather than contribution",
            f'{len(facts["weak_opener_bullets"])} bullets open with a duty phrase, e.g. '
            f'"{facts["weak_opener_bullets"][0][:90]}"',
            guidance="Rework these around what you personally did and what changed because "
                     f"of it, rather than what you were responsible for{for_role}.",
        ))

    # Substance, not just structure. Every other tier-2 check looks at how a
    # bullet OPENS; this one looks at whether it ever arrives at a result. Without
    # it a tidy but hollow CV - bullets present, sections complete, no typos -
    # comes back with almost nothing to fix, which is the wrong answer at scale.
    total_exp = facts.get("experience_bullets", 0)
    with_outcome = facts.get("experience_bullets_with_outcome", 0)
    if total_exp >= 4 and with_outcome / total_exp < 0.4:
        example = (facts.get("bullets_without_outcome") or [""])[0][:90]
        issues.append(_issue(
            2, "no_outcomes", "Most bullets describe the task but not the result",
            f"{total_exp - with_outcome} of {total_exp} experience bullets contain no "
            f'outcome, figure or change, e.g. "{example}"',
            guidance="For each one, add what changed because you did it — faster, cheaper, "
                     "clearer, larger, or a decision that followed. Use a number only where "
                     "you genuinely have one; an invented figure is worse than none.",
        ))

    # --- Tier 3: structure and consistency -----------------------------------
    writing = facts["heading_typos"] + facts["month_typos"]
    if writing:
        issues.append(_issue(
            3, "typos", "Typos in headings or dates",
            "; ".join(str(w) for w in writing[:4]),
            guidance="These are quick to fix and they are the kind of thing a reader "
                     "notices immediately.",
        ))
    if facts["mixed_spelling"]:
        issues.append(_issue(
            3, "spelling_variant", "British and American spelling are mixed",
            "Both forms appear: " + ", ".join(facts["mixed_spelling"]),
            guidance="Pick one convention and apply it throughout.",
        ))
    if facts["bullet_punctuation_mixed"]:
        issues.append(_issue(
            3, "bullet_punctuation", "Bullet punctuation is inconsistent",
            "Some bullets end with a full stop and others do not.",
            guidance="Choose one and make every bullet match.",
        ))
    if facts["education_after_experience"]:
        issues.append(_issue(
            3, "education_order", "Education comes after work experience",
            "Section order: " + " → ".join(facts["section_order"]),
            guidance="For a student CV, education normally comes first. The exception is a "
                     "mature student with several years of directly relevant work.",
        ))
    # Findings of the same kind are collapsed into one issue. Four separate gap
    # findings would otherwise consume the whole five-slot cap and crowd out more
    # damaging problems - which is exactly what happened on review.
    overlaps = [f for f in date_findings if f["kind"] == "overlap"]
    gaps = [f for f in date_findings if f["kind"] == "gap"]
    if overlaps:
        issues.append(_issue(
            3, "date_overlap",
            "Two entries cover the same period" if len(overlaps) == 1
            else f"{len(overlaps)} pairs of entries cover the same period",
            " ".join(f["text"] for f in overlaps[:3]),
            section=overlaps[0].get("section"), guidance="",
        ))
    if gaps:
        issues.append(_issue(
            3, "date_gap",
            "An unexplained gap in the timeline" if len(gaps) == 1
            else f"{len(gaps)} unexplained gaps in the timeline",
            " ".join(f["text"] for f in gaps[:3]),
            section=gaps[0].get("section"), guidance="",
        ))
    if facts["table_count"]:
        issues.append(_issue(
            3, "tables", "The layout uses tables",
            f'{facts["table_count"]} table(s) detected.',
            guidance="Tables are a common cause of scrambled parsing when a CV is read "
                     "automatically. A plain single-column layout is safer.",
        ))

    # --- Tier 4: missing sections and length ---------------------------------
    for name in facts["missing_standard_sections"]:
        issues.append(_issue(
            4, f"missing_{name}", f"No {name} section found",
            f"Nothing in the document reads as a {name} section.",
            guidance=f"If you have {name.lower()} worth showing, add it.",
        ))
    if facts["too_long"]:
        issues.append(_issue(
            4, "too_long", f"The CV runs to {facts['page_count']} pages",
            f"{facts['page_count']} pages.",
            guidance="One page, two at most, is the expectation for a student CV in this "
                     "market. Cut what is least relevant to the role.",
        ))

    # --- Tier 5: detail-level ------------------------------------------------
    if facts["grade_notes"]:
        issues.append(_issue(
            5, "grades", "Grades need clarifying",
            " ".join(facts["grade_notes"]),
            section=education_section, guidance="",
        ))
    if facts["grade_consistency"]:
        issues.append(_issue(
            5, "grade_consistency", "Grades are shown for some degrees but not others",
            facts["grade_consistency"], section=education_section,
            # The reason is the part that persuades a student to act. Left in the
            # evidence text it gets summarised away into "can raise questions";
            # as guidance it is something the model has to render.
            # The reason is carried by report.deterministic_notes so it survives
            # verbatim; repeating it here produced it twice in one report.
            guidance="Show a grade for every education entry, or for none of them.",
        ))
    # The language ladder Career Services asked for. It has to be an issue rather
    # than a style note, otherwise it can neither be raised nor change the
    # section's status - which is why a section reading "English: Proficient"
    # kept coming back Strong with no nudge at all.
    languages = facts.get("language_levels") or {}
    if languages.get("missing"):
        issues.append(_issue(
            5, "language_no_level", "Languages are listed without a level",
            "No level given for: " + ", ".join(languages["missing"][:4]),
            section=languages.get("section"),
            guidance="Put a plain label against each one first (Basic, Intermediate, "
                     "Advanced, Fluent) so a reader can act on it — then consider CEFR "
                     "(A1-C2), which is the precise form recruiters read the same way "
                     "everywhere.",
        ))
    elif languages.get("plain_only"):
        issues.append(_issue(
            5, "language_plain_only", "Language levels could be more precise",
            "Plain labels used, no CEFR: " + ", ".join(languages["plain_only"][:4]),
            section=languages.get("section"),
            guidance="Consider upgrading these to CEFR (A1-C2). A recruiter reads \"B2\" "
                     "the same way in every country; \"Proficient\" means different things "
                     "to different readers. State the level you are genuinely at now, not "
                     "the last certificate you sat.",
        ))

    if facts.get("single_word_interests"):
        issues.append(_issue(
            5, "bare_interests", "Interests are listed without any detail",
            "Listed as bare words: " + ", ".join(facts["single_word_interests"][:5]),
            section=facts.get("single_word_interests_section"),
            guidance="Say what kind, how often, and to what level. \"Chess\" says nothing; "
                     "a club, a rating or a regular commitment says something.",
        ))
    if facts["buzzwords"]:
        issues.append(_issue(
            5, "buzzwords", "Trait words with nothing behind them",
            "Listed without evidence: " + ", ".join(facts["buzzwords"]),
            section=skills_section,
            guidance="These belong in the experience bullets as something you demonstrably "
                     "did, not in a list of adjectives. A reader discounts them otherwise.",
        ))

    issues.sort(key=lambda i: i["tier"])

    # A section carrying any issue cannot be reported as strong. This is what
    # stops the report contradicting itself between section 4 and section 5.
    status = {}
    flagged = {i["section"] for i in issues if i["section"]}
    for section in facts["sections"]:
        status[section["heading"]] = (
            "needs_attention" if section["heading"] in flagged else "strong"
        )

    return {
        "key_areas": issues[:MAX_KEY_AREAS],
        "all_issues": issues,
        "section_status": status,
        "dropped_from_key_areas": issues[MAX_KEY_AREAS:],
        "strengths": strengths(facts),
    }


def describe_for_prompt(result: dict) -> str:
    """The ranked issue list handed to the report model."""
    if not result["all_issues"]:
        return ("ISSUES FOUND: none. This CV has no measured problems. Say so plainly and "
                "do not manufacture improvement areas to fill the section.")

    out = ["RANKED ISSUES (found in the document, ordered most damaging first). Write the "
           "'Key areas to improve' section from the KEY AREAS below, in this order, one "
           "entry each - no more, no fewer. Do not add an area that is not listed here."]
    out.append("\nKEY AREAS (use exactly these):")
    for n, issue in enumerate(result["key_areas"], 1):
        out.append(f'  {n}. [tier {issue["tier"]}] {issue["title"]}')
        out.append(f'     evidence: {issue["evidence"]}')
        if issue["guidance"]:
            out.append(f'     what the student should do: {issue["guidance"]}')
        if issue["section"]:
            out.append(f'     belongs to section: "{issue["section"]}"')

    if result["dropped_from_key_areas"]:
        out.append("\nLOWER-PRIORITY ISSUES (do NOT put these in Key areas - they were cut "
                   "by the cap - but DO cover each one in the relevant section's detail):")
        for issue in result["dropped_from_key_areas"]:
            out.append(f'  - [tier {issue["tier"]}] {issue["title"]}: {issue["evidence"]}')
            # The guidance has to travel with a dropped issue too. Without it the
            # model saw only the bare fact and wrote the rule without its reason -
            # "leaving some out can raise questions" instead of "a recruiter
            # assumes the grade you left out was the bad one".
            if issue["guidance"]:
                out.append(f'      what the student should do: {issue["guidance"]}')
            if issue["section"]:
                out.append(f'      belongs to section: "{issue["section"]}"')

    if result.get("strengths"):
        out.append("\nMEASURED STRENGTHS. Write 'what works well' from these and ONLY these. "
                   "You may reword them for a student; you may not add one, and you may not "
                   "claim anything about how valuable or well regarded something is:")
        for item in result["strengths"]:
            out.append(f"  - {item}")
    else:
        out.append("\nMEASURED STRENGTHS: none. Return an empty 'what_works_well' array. "
                   "Do not invent praise to fill the section.")

    out.append("\nSECTION STATUS (decided from the issues above - use exactly these, they "
               "cannot disagree with the key areas):")
    for heading, value in result["section_status"].items():
        out.append(f'  - "{heading}": {value}')
    return "\n".join(out)
