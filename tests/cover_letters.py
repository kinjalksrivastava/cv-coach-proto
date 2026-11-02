"""
The cover letter side: its own personal-data layer, its length check, the order
of its PDF, and what section 5 of the CV report puts in front of a student.

Every case here comes from round 5 of Career Services' review, or from a failure
found while fixing one of those. Offline - no model call, no network.

    ./venv/bin/python tests/cover_letters.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cover_letter  # noqa: E402
import hsg_activities  # noqa: E402
import letter_pii  # noqa: E402
import report  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(name: str, problems: list[str]) -> None:
    global CHECKS
    CHECKS += 1
    if problems:
        FAILURES.append(name)
        print(f"FAIL  {name}")
        for problem in problems:
            print(f"        {problem}")
    else:
        print(f"ok    {name}")


# --- the letters -------------------------------------------------------------

ADDRESSED = """Max Mustermann
Rosenbergstrasse 12
9000 St. Gallen
max.mustermann@student.unisg.ch

Stadler Rail AG
z. Hd. Anna-Sophia Schmitz
Deputy CHRO Division Service
Ernst-Stadler-Strasse 4
9565 Bussnang

Application for the International Management Trainee Programme

Dear Ms Schmitz

Since childhood I have been fascinated by the mobility sector. At START Global I
built a new team from scratch. I would be glad to discuss this with you,
Ms Schmitz.

Yours sincerely
Max Mustermann
"""

ADDRESS_BLOCK_ONLY = """Lena Bachmann
lena.bachmann@student.unisg.ch

Roche Holding AG
Sarah Widmer
Talent Acquisition
4058 Basel

Dear Sir or Madam

I am applying for the Finance Graduate Programme. My Bachelor at the University
of St. Gallen gave me the quantitative grounding the role asks for.

Kind regards
Lena Bachmann
"""

NO_CONTACT_BLOCK_DE = """Sehr geehrte Frau Hofmann

Mit grossem Interesse bewerbe ich mich auf die Stelle als Trainee bei der
Credit Suisse AG. Waehrend meines Studiums an der Universitaet St. Gallen habe
ich ein Team aufgebaut.

Mit freundlichen Gruessen
Jonas Keller
"""

NOBODY_NAMED = """Dear Hiring Team

I am writing to apply for the Consulting Internship at Bain & Company. During my
studies at the University of St. Gallen I led the Consulting Club case team.

Yours faithfully
Nina Frei
"""


def recipient_cases() -> None:
    """
    MP, round 5: asked who the letter was addressed to, the bot answered with
    the name and the job title of a real person at a real company. The CV layer
    had no reason to look for a second person.
    """
    out = letter_pii.strip_letter_pii(ADDRESSED, "en")
    text = out["text"]
    check("recipient named on an attention line and in the salutation", [
        p for p in [
            "'Schmitz' survived" if "Schmitz" in text else "",
            "'Anna-Sophia' survived" if "Anna-Sophia" in text else "",
            "the attention marker was removed with the name"
            if "z. Hd." not in text else "",
            "the salutation was removed with the name" if "Dear" not in text else "",
            "the company was removed" if "Stadler Rail AG" not in text else "",
            "nothing was reported as redacted"
            if "name of the recipient" not in out["redactions"] else "",
            f"residual: {out['residual']}" if out["residual"] else "",
        ] if p])

    out = letter_pii.strip_letter_pii(ADDRESS_BLOCK_ONLY, "en")
    text = out["text"]
    check("recipient named only in the address block", [
        p for p in [
            "'Widmer' survived" if "Widmer" in text else "",
            "the company was removed" if "Roche Holding AG" not in text else "",
            "a generic salutation was redacted"
            if "Dear Sir or Madam" not in text else "",
        ] if p])

    out = letter_pii.strip_letter_pii(NOBODY_NAMED, "en")
    text = out["text"]
    check("a letter that names nobody is not told otherwise", [
        p for p in [
            "the salutation was rewritten" if "Dear Hiring Team" not in text else "",
            "a recipient was reported where there is none"
            if "name of the recipient" in out["redactions"] else "",
        ] if p])


def author_signoff() -> None:
    """
    Found by these tests, not by the reviewers. A CV always opens with a contact
    block, so the CV layer learns the author's name from the top of the page. A
    letter need not have one, and then the only place the author is named is
    under the sign-off.
    """
    for label, letter, language, name in (
        ("german, no contact block", NO_CONTACT_BLOCK_DE, "de", "Keller"),
        ("english, no contact block", NOBODY_NAMED, "en", "Frei"),
    ):
        out = letter_pii.strip_letter_pii(letter, language)
        check(f"the author's own name under the sign-off ({label})", [
            p for p in [
                f"'{name}' survived" if name in out["text"] else "",
                "the sign-off itself was removed"
                if not re.search(r"(Gruessen|faithfully)", out["text"]) else "",
            ] if p])


def facts_still_measurable() -> None:
    """
    The checks in analyse() run on the redacted text. A redaction that blanks
    the salutation or the company block would make the report tell the student
    their letter is missing something it has.
    """
    text = letter_pii.strip_letter_pii(ADDRESSED, "en")["text"]
    facts = cover_letter.analyse(text, "", "Management Trainee Programme", "")
    check("redaction does not destroy what the letter is measured on", [
        p for p in [
            "salutation reported missing" if not facts["has_salutation"] else "",
            "sign-off reported missing" if not facts["has_closing"] else "",
            "recipient block reported missing"
            if not facts["has_recipient_block"] else "",
            "the role is reported as unnamed" if not facts["names_the_role"] else "",
        ] if p])


def length_is_counted_not_guessed() -> None:
    """
    Round 5, both directions in the same week: 581 words called "runs past one
    page" on a letter that fits one page (MP), and 429 words called "fits
    comfortably on one page" on a letter that ran onto a second (SS). Both from
    dividing words by an assumed words-per-page.
    """
    body = " ".join(["Beitrag"] * 400)
    strings = cover_letter.STRINGS["en"]
    rows = {}
    for label, pages in (("one page", 1), ("two pages", 2), ("not countable", None)):
        facts = cover_letter.analyse(body, "", "Trainee", "", page_count=pages)
        rows[label] = cover_letter._measured_rows(facts, strings)["length"]

    problems = []
    if "581" in rows["one page"] or re.search(r"\b\d{3}\b", rows["one page"]):
        problems.append(f"a word count is still being quoted: {rows['one page']}")
    if "2 pages" not in rows["two pages"]:
        problems.append(f"the real page count is not used: {rows['two pages']}")
    for label in ("one page", "not countable"):
        if re.search(r"runs (past|to)", rows[label]):
            problems.append(f"{label} is claimed to run over: {rows[label]}")
    if "could not be measured" not in rows["not countable"]:
        problems.append(f"an unmeasurable length is not said to be: {rows['not countable']}")
    check("length comes from the page count, never from a word count", problems)

    fact_line = cover_letter._length_fact(
        cover_letter.analyse(body, "", "", "", page_count=None))
    check("the model is not handed a page estimate either",
          [] if "not measurable" in fact_line else [f"the model is told: {fact_line}"])


def very_short_still_caught() -> None:
    """One page and nearly empty is still one page. Words say what pages cannot."""
    facts = cover_letter.analyse("Dear Sir or Madam. I would like the job.", "",
                                 "Trainee", "", page_count=1)
    row = cover_letter._measured_rows(facts, cover_letter.STRINGS["en"])["length"]
    check("a nearly empty letter is not called the right length",
          [] if "very little" in row else [f"reported as: {row}"])


def both_languages_complete() -> None:
    missing = []
    for language, strings in cover_letter.STRINGS.items():
        for other, reference in cover_letter.STRINGS.items():
            if other == language:
                continue
            for key in reference:
                if key not in strings:
                    missing.append(f"{language} is missing '{key}'")
    check("every string exists in both languages", sorted(set(missing)))


def pdf_sections_in_order() -> None:
    """
    MP, round 5: "The PDF report of the cover letter shows the wrong order:
    nothing under 2. and falsely shows it in section 3." The table was built
    under its heading and appended after the next section.
    """
    try:
        import pdfplumber
    except ImportError:
        print("skip  pdf section order (pdfplumber not installed)")
        return
    from io import BytesIO

    strings = cover_letter.STRINGS["en"]
    facts = cover_letter.analyse("word " * 300, "", "Trainee", "", page_count=1)
    data = {"overall_assessment": "A clear letter.",
            "essentials": {k: f"Feedback on {k}." for k in
                           ["adds_value", "why_organisation", "why_role",
                            "what_you_bring", "conclusion"]}}
    blob = cover_letter.to_pdf(data, facts, strings)
    if not blob:
        print("skip  pdf section order (reportlab not installed)")
        return
    with pdfplumber.open(BytesIO(blob)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    order = [("2. " + strings["essentials"]), strings["labels"]["adds_value"],
             ("3. " + strings["guidance_heading"])]
    found = [text.find(piece) for piece in order]
    problems = [f"not in the PDF at all: {piece}"
                for piece, index in zip(order, found) if index == -1]
    if not problems and found != sorted(found):
        problems.append("the essentials table is not under its own heading: "
                        f"positions {found} for {order}")
    check("the letter PDF puts the table under section 2", problems)


def no_relevance_claim_without_an_advert() -> None:
    """
    MP, round 5. The prompt carries the rule and held for two of the three
    sample letters; on the third the model wrote "skills relevant to the
    position" with no advert uploaded. This is the enforcement behind it.
    """
    data = {"overall_assessment": "It shows skills relevant to the position.",
            "essentials": {"what_you_bring": "Experience relevant for the trainee role.",
                           "why_role": "Das ist relevant für die Stelle.",
                           "conclusion": "A polite close."}}
    cleaned = cover_letter._without_role_claims(data)
    written = " ".join([cleaned["overall_assessment"]] + list(cleaned["essentials"].values()))
    problems = [f"survived: '{claim}'" for claim in
                ("relevant to the position", "relevant for the trainee role",
                 "relevant für die Stelle") if claim.lower() in written.lower()]
    if "A polite close." not in written:
        problems.append("a sentence with no claim in it was rewritten anyway")
    check("no claim of relevance when no advert was uploaded", problems)


def section_five_picks() -> None:
    """
    MP, round 5: section 5 should name the clubs and the Additional
    Qualification programmes, which are in most cases more relevant to a job
    than HSG University Sports. SS, round 5: the italic "Belongs in" tails are
    instructions for the bot and should not be printed to the student.
    """
    picks = [name for name, *_ in hsg_activities.closing_suggestions()]
    problems = []
    if not any("student clubs" in name for name in picks):
        problems.append(f"the clubs are not offered by default: {picks}")
    if not any("Additional Qualification" in name for name in picks):
        problems.append(f"the qualification programmes are not offered: {picks}")
    if "My HSG Career" in picks:
        problems.append("a job board is suggested as something to add to a CV")
    check("section 5 leads with the clubs and the qualification programmes", problems)

    rendered = report.render_markdown(
        {"overall_impression": "x", "sections": []}, [], report.STRINGS["en"],
        hsg_picks=hsg_activities.closing_suggestions())
    check("the report does not print the bot's own placement instructions",
          ["'Belongs in' is still rendered"] if "Belongs in" in rendered else [])


def run() -> int:
    recipient_cases()
    author_signoff()
    facts_still_measurable()
    length_is_counted_not_guessed()
    very_short_still_caught()
    both_languages_complete()
    no_relevance_claim_without_an_advert()
    pdf_sections_in_order()
    section_five_picks()
    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(run())
