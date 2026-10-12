"""
Every sample CV, through the real pipeline, checked against everything Career
Services asked for.

The edge-case suite runs offline and pins the parser. This one is the opposite:
it makes the real model calls, builds the real report, and then reads that
report back looking for the specific faults Serena and Miriam reported. It is
slow and it costs money, so it is not part of the normal loop - run it before
handing a build to them.

    ./venv/bin/python tests/full_sweep.py            # all of them
    ./venv/bin/python tests/full_sweep.py 4          # the first four, while iterating

Every check below is a sentence from one of their documents.
"""

import os
import re
import sys
import glob
import tomllib
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI                                            # noqa: E402
import bullet_review, cv_facts, date_review, format_check            # noqa: E402
import hsg_activities, report, severity                              # noqa: E402
from extraction import extract_text                                  # noqa: E402
from guardrails import language, section_coverage                    # noqa: E402
from pii import strip_pii                                        # noqa: E402

MODEL = "gpt-4.1"
SAMPLES = os.path.expanduser("~/Downloads/CV Samples")

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PROFILE = re.compile(r"(?:linkedin|xing|github)\.com/[\w\-./]+", re.I)
PHONE = re.compile(r"\+\d{1,3}[\s\-./]?\d[\d\s\-./]{7,}\d")
# A bracketed blank: the rewriting loophole. A markdown link is "[text](url)",
# so the negative lookahead keeps the HSG links out of this.
TEMPLATE = re.compile(r"\[[^\]\n]{4,}\](?!\()")
# English furniture in a German report. Deliberately only the words this
# project controls - "Format-Check" and "Status" are ordinary German, and the
# HSG programme names stay English because they are proper nouns.
GERMAN_REPORT_ENGLISH = re.compile(
    r"\b(Needs attention|Not assessable|Overall impression|What works well|"
    r"Key areas to improve|Section-by-section feedback|Dates worth a look|"
    r"Spelling and consistency|Estimated ATS compatibility|Comment\b)\b")


def _orphans(cv_text: str, sections: list) -> str:
    """The first line of content that no section covers."""
    covered = set()
    for block in cv_facts._split_sections(cv_text, sections):
        covered.update(range(block["start"], block["end"]))
    for index, line in enumerate(cv_text.splitlines()):
        if index not in covered and line.strip() and "REDACTED" not in line \
                and "REMOVED" not in line:
            return line.strip()[:60]
    return ""


def audit(path: str) -> dict:
    name = os.path.relpath(path, SAMPLES)
    problems = []
    client = OpenAI(api_key=tomllib.load(open(".streamlit/secrets.toml", "rb"))["OPENAI_API_KEY"])

    res = extract_text(open(path, "rb").read(), os.path.basename(path))
    if not res.ok:
        return {"name": name, "problems": [f"extraction failed: {res.error[:60]}"]}

    doc_lang = language.detect_message_language(res.text) or "en"
    clean = strip_pii(res.text, doc_lang)
    cv_text = clean["text"]

    # 1. PRIVACY. "We need ABSOLUTE privacy."
    if clean["residual"]:
        problems.append(f"PRIVACY residual after the gate: {clean['residual']}")

    sections = section_coverage.detect_sections(cv_text, client, MODEL)
    facts = cv_facts.analyse(
        cv_text, res.meta, sections, None, doc_lang,
        lambda items: bullet_review.review(client, MODEL, items, report.SECTION_RULES),
        lambda doc: date_review.read(client, MODEL, doc),
        doc_lang)
    ranked = severity.assess(facts)
    rows = format_check.run(cv_text, res.meta, facts, doc_lang)

    # 2. THE WHOLE CV IS BEING ANALYSED. Not "did it parse" but "how much of the
    #    document ended up inside a section the report can talk about". Anything
    #    outside every section is content nobody is reading.
    # No sections at all is allowed ONLY if the report says so out loud.
    if not sections and "no_sections" not in {i["key"] for i in ranked["all_issues"]}:
        problems.append("PARSE no sections found, and the report does not say so")
    entries = sum(s["entry_count"] for s in facts["sections"])
    if sections and not entries and not facts["total_bullets"]:
        problems.append("PARSE sections found but no entries and no bullets")

    real_lines = [l for l in cv_text.splitlines()
                  if l.strip() and "REDACTED" not in l and "REMOVED" not in l]
    lines = cv_text.splitlines()
    covered = set()
    for block in cv_facts._split_sections(cv_text, sections):
        covered.update(range(block["start"], min(block["end"], len(lines))))
    inside = len([i for i in covered
                  if lines[i].strip() and "REDACTED" not in lines[i]
                  and "REMOVED" not in lines[i]])
    coverage = inside / max(1, len(real_lines))
    if coverage < 0.75 and not facts.get("no_sections_found"):
        orphan = _orphans(cv_text, sections)
        problems.append(
            f"COVERAGE only {coverage:.0%} of the CV sits inside a section"
            + (f"; first line outside: {orphan!r}" if orphan else ""))

    # Every heading-shaped line the vocabulary recognises must be among the
    # sections, otherwise a whole section is being skipped.
    known = {section_coverage.heading_lookup.normalise(s["heading"]) for s in sections}
    for line in cv_text.splitlines():
        entry = section_coverage.heading_lookup.identify(line.strip())
        if (entry and section_coverage.heading_lookup._heading_shaped(line)
                and section_coverage.heading_lookup.normalise(entry["clean"]) not in known):
            problems.append(f"SECTIONS heading not picked up: {line.strip()[:40]!r}")
            break


    data = report.generate(client, MODEL, cv_text, "", "", rows, facts, ranked,
                           language.SUPPORTED[doc_lang])
    if not data:
        return {"name": name, "problems": problems + ["REPORT generation failed"]}

    strings = dict(report.STRINGS[doc_lang])
    strings["criteria_note"] = format_check.criteria_note(doc_lang)
    notes = report.deterministic_notes(facts, doc_lang)
    picks = hsg_activities.closing_suggestions(
        "", cv_text, section_status=ranked["section_status"],
        missing_sections=facts.get("missing_report_sections"),
        categories={s["heading"]: s["category"] for s in sections})
    md = report.render_markdown(data, rows, strings, facts["date_findings"], notes,
                                picks, ranked["section_status"])
    pdf = report.to_pdf(data, rows, strings, facts["date_findings"], notes, picks,
                        ranked["section_status"])

    # 3. PRIVACY, again, on the finished report rather than the input.
    for label, pattern in (("email", EMAIL), ("profile url", PROFILE), ("phone", PHONE)):
        hit = pattern.search(md)
        if hit:
            problems.append(f"PRIVACY {label} in the report: {hit.group(0)[:40]!r}")

    # 4. SECTION 3 IS GONE. "'What works well' should still be removed."
    if strings["works_well"] in md:
        problems.append("SECTION 3 'what works well' is still in the report")
    headings = [h.strip() for h in re.findall(r"^### (.+)$", md, re.M)]
    numbers = [int(m.group(1)) for h in headings if (m := re.match(r"(\d+)\.", h))]
    if numbers != sorted(numbers) or numbers[:3] != [1, 2, 3]:
        problems.append(f"REPORT section numbering is {numbers}")

    # 5. NO EXAMPLE BULLETS. The rewriting loophole, in the report this time.
    for match in TEMPLATE.finditer(md):
        if "REDACTED" in match.group(0) or "REMOVED" in match.group(0):
            continue
        problems.append(f"REWRITING bracketed blank in the report: {match.group(0)[:50]!r}")
        break

    # 6. BULLET EXAMPLES ARE OFFERED AND REFERENCED.
    if strings["bullet_pointer"] not in md:
        problems.append("BULLETS the worked-examples pointer is missing")
    if pdf and len(pdf) < 4000:
        problems.append("PDF suspiciously small - the appendix may be missing")

    # 7. DATES ONLY IN THEIR OWN SECTION. "Gaps should only be addressed in
    #    section 5 - dates worth a look."
    if any(i["key"] in severity.DATE_KEYS for i in ranked["key_areas"]):
        problems.append("DATES a gap or overlap is competing for a key-area slot")
    if any(i["key"] in severity.FORMAT_CHECK_KEYS for i in ranked["key_areas"]):
        problems.append("DUPLICATION a format-check row is repeated as a key area")

    # 8. WEAKNESSES ARE SHOWN. No section called Strong while something names it,
    #    and nothing called Strong on a CV with no bullets at all.
    flagged = {i["section"] for i in ranked["all_issues"]
               if i["section"] and i["key"] not in severity.DATE_KEYS}
    for heading, status in ranked["section_status"].items():
        if status == "strong" and heading in flagged:
            problems.append(f"STRONG '{heading}' is Strong but an issue names it")
    if facts["has_no_bullets_anywhere"]:
        describing = [s["heading"] for s in facts["sections"]
                      if s["category"] in severity.DETAIL_CATEGORIES and s["entry_count"]]
        for heading in describing:
            if ranked["section_status"].get(heading) == "strong":
                problems.append(f"STRONG '{heading}' is Strong with no bullets anywhere")
    # And the rendered table must agree with the computed status.
    for section in (data.get("sections") or []):
        computed = ranked["section_status"].get(str(section.get("name", "")).strip())
        if computed and f"| {section['name']} | " in md:
            row = next(l for l in md.splitlines() if l.startswith(f"| {section['name']} |"))
            word = strings.get("lang") and report.STATUS_WORDS[doc_lang][computed]
            if word not in row:
                problems.append(f"STRONG rendered status for '{section['name']}' "
                                f"disagrees with the computed one")

    # 9. THE DISCLAIMERS ARE THERE.
    if format_check.criteria_note(doc_lang)[:40] not in md:
        problems.append("DISCLAIMER the ATS explainer is missing")

    # 10. ATS. No correct heading reported as unrecognisable.
    ats = next(r["comment"] for r in rows if "ATS" in r["check"] or "ATS" in r["check"])
    unknown = re.search(r"(?:may not recognise|nicht erkennen) \(([^)]*)\)", ats)
    if unknown:
        # Headings are quoted in the message because one can contain a comma.
        for heading in re.findall(r'"([^"]+)"', unknown.group(1)):
            entry = section_coverage.heading_lookup.identify(heading)
            if entry and entry["damage"] is None:
                problems.append(f"ATS flags the standard heading {heading!r}")

    # 11. BOTH LANGUAGES. A German report must not carry English furniture.
    if doc_lang == "de":
        hit = GERMAN_REPORT_ENGLISH.search(md)
        if hit:
            problems.append(f"LANGUAGE English in a German report: {hit.group(0)!r}")

    # 12b. THE PROSE ITSELF. Every complaint Career Services made came from
    #      reading a generated report, so the report text is read back for the
    #      things they objected to, not just its structure.
    low = md.lower()

    # "It should not suggest volunteer roles in the work experience."
    for block in re.split(r"\n\*\*", md.split("\n### ")[0] if False else md)[1:]:
        block = block.split("\n### ")[0]          # stop at the next report section
        head = block.split("**")[0].lower()
        if any(w in head for w in ("work experience", "professional experience",
                                   "berufserfahrung", "beruflicher werdegang")):
            if re.search(r"volunteer|ehrenamt|freiwillig", block, re.I):
                problems.append("CONTENT volunteering suggested under work experience")
            break

    # "Don't suggest a specific number of bullet points."
    if re.search(r"(two|three|2|3)\s*[-–]\s*(three|four|3|4)\s+bullet|"
                 r"(two|three|zwei|drei)\s+bullet|\d\s*[-–]\s*\d\s+(bullet|stichpunkt)",
                 low):
        problems.append("CONTENT a specific number of bullet points is suggested")

    # "They should not explain where they have used the technical skills."
    if re.search(r"(where|wo)\s+you\s+(have\s+)?used|erkl[äa]re?,?\s+wo\s+du", low):
        problems.append("CONTENT asks the student to explain where a skill was used")

    # "Extracurriculars shouldn't be mentioned in hobbies and interests."
    for block in re.split(r"\n\*\*", md)[1:]:
        block = block.split("\n### ")[0]          # stop at the next report section
        head = block.split("**")[0].lower()
        # Interests ONLY. A combined heading like "VOLUNTEERING, SOCIETIES &
        # INTERESTS" is an extracurricular section too, and a club genuinely
        # belongs there.
        if ("hobb" in head or "interest" in head or "interessen" in head) and not any(
                w in head for w in ("volunteer", "societ", "extracurricular", "club",
                                    "ehrenamt", "engagement", "aktivit")):
            # The complaint was about HSG activities being proposed here, not
            # about the word "club". "What kind, how often, to what level (e.g.
            # club membership)" is detail about an interest, which is exactly
            # what Career Services asked for.
            if re.search(r"shsg\.ch|unisg\.ch|HSG (student )?club|Consulting Club|"
                         r"Helvetian Investment|oikos|START Summit|Symposium",
                         block, re.I):
                problems.append("CONTENT an HSG activity is suggested under hobbies")
            break

    # "Since personal details are removed when parsing, it should not comment on them."
    if re.search(r"(add|include|ergänze|füge)[^.]{0,40}"
                 r"(contact details|personal details|date of birth|nationality|"
                 r"persönliche (daten|angaben)|geburtsdatum|adresse)", low):
        problems.append("CONTENT comments on personal details")

    # "The bot still uses american rather than British English."
    if doc_lang == "en":
        us = re.findall(r"\b(organiz\w+|analyz\w+|special[iy]z\w+|recogniz\w+|"
                        r"emphasiz\w+|summariz\w+|\bresume\b|\bcenter\b|\bcolor\b)\b", low)
        # The CV's own wording is quoted back as evidence, so only flag words
        # that do not appear in the document itself.
        invented = [w for w in set(us) if w not in cv_text.lower()]
        if invented:
            problems.append(f"CONTENT American spelling in the report: {sorted(invented)[:3]}")

    # "Instead of 'use it to briefly state your academic focus'..." Only inside
    # a profile block: the same words describing a degree specialisation are
    # fine, and were being flagged.
    for block in re.split(r"\n\*\*", md)[1:]:
        block = block.split("\n### ")[0]
        head = block.split("**")[0].lower()
        if "profile" in head or "kurzprofil" in head or "summary" in head:
            if re.search(r"academic focus|akademische[nr]? schwerpunkt", block, re.I):
                problems.append("CONTENT the old profile wording is back")
            break

    # 12. NOTHING SAID TWICE. The same sentence in a key area and a section.
    key_detail = {str(a.get("detail", "")).strip().lower()
                  for a in (data.get("areas_to_improve") or []) if a.get("detail")}
    for section in (data.get("sections") or []):
        for point in (section.get("points") or []):
            if str(point).strip().lower() in key_detail:
                problems.append("DUPLICATION a key area is repeated verbatim in a section")
                break

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, name.replace("/", "__") + ".md"), "w",
              encoding="utf-8") as handle:
        handle.write(md)

    return {"name": name, "problems": problems, "lang": doc_lang,
            "sections": len(sections), "entries": entries, "coverage": coverage,
            "bullets": facts["total_bullets"], "issues": len(ranked["all_issues"])}


def main() -> int:
    files = sorted(glob.glob(f"{SAMPLES}/**/*.pdf", recursive=True)
                   + glob.glob(f"{SAMPLES}/**/*.docx", recursive=True))
    if len(sys.argv) > 1:
        files = files[:int(sys.argv[1])]

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(audit, files))

    failed = 0
    for item in sorted(results, key=lambda r: r["name"]):
        if item["problems"]:
            failed += 1
            print(f"\nFAIL  {item['name']}")
            for problem in item["problems"]:
                print(f"        {problem}")
        else:
            print(f"ok    {item['name']:<46} {item.get('lang')}  "
                  f"sections={item.get('sections')} entries={item.get('entries')} "
                  f"bullets={item.get('bullets')} issues={item.get('issues')} "
                  f"covered={item.get('coverage', 0):.0%}")
    print(f"\n{len(results) - failed}/{len(results)} CVs clean")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
