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

import cover_letter
import prompts  # noqa: E402
import hsg_activities  # noqa: E402
import letter_pii  # noqa: E402
import pii  # noqa: E402
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


def addresses_in_every_format() -> None:
    """
    Found by tests/pii_audit.py, not by a reviewer. Every address pattern was
    continental and anchored tightly, so "CH- 9004 St. Gallen" survived on the
    one space after the hyphen, and "Pittsburgh, PA 15213" survived because
    nothing here had ever seen a US address. A Swiss university has students
    applying abroad.
    """
    cases = [
        ("CH- 9004 St. Gallen", True), ("CH-9000 St. Gallen", True),
        ("9000 St. Gallen", True), ("Pittsburgh, PA 15213", True),
        ("New York, NY 10001-1234", True), ("London EC1A 1BB", True),
        ("5th August 2024", False), ("Ref.: 22384739724", False),
        ("Modern Technology AG", False),
    ]
    problems = []
    for text, should_go in cases:
        _, hit = pii._sub_address(text)
        if hit != should_go:
            problems.append(f"{text!r}: redacted={hit}, expected {should_go}")
    check("an address is removed whatever country it is written for", problems)


def recipient_job_title_and_honorific() -> None:
    """
    Round 5 named the recipient AND their job title. The name goes by name; the
    title goes because of where it sits, directly under the person in the
    address block, where nothing but the parties and the organisation belongs.
    """
    out = letter_pii.strip_letter_pii(ADDRESSED, "en")["text"]
    problems = []
    if "Deputy CHRO" in out:
        problems.append("the recipient's job title survived")
    if "Stadler Rail AG" not in out:
        problems.append("the company went with it")
    if re.search(r"\bMs\s+\[", out):
        problems.append("an honorific was left in front of the redaction")
    check("the recipient's title goes, the organisation stays", problems)


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


# --- Cover Letter Feedback Rules v2 ------------------------------------------
#
# The three worked examples in section 2 of v2 are the only labelled data
# Career Services have given us for the most important check in the brief, and
# the third is labelled TWICE, once for each of two CVs. They are therefore
# treated here the way the hand-labelled CVs are treated on the other side: as
# ground truth the measurements have to reproduce, not as illustrations.

CV_SAYS_LITTLE = """Education
University of St. Gallen, BA Business Administration, 2021-2024
Experience
UBS, Summer Intern, Investment Banking: financial analysis, valuation and
market research.
Student Union, treasurer: managed a budget of CHF 40000 and ran the elections.
"""

CV_SAYS_IT_ALL = """Education
University of St. Gallen, BA Business Administration, 2021-2024
Experience
UBS, Summer Intern, Investment Banking: benchmarked valuation multiples against
peers to identify mispricing and valuation drivers; presented findings to senior
colleagues. Prepared client presentations and financial analysis.
Student Union, treasurer: managed a budget of CHF 40000 and ran the elections.
"""

# Section 2, "NOT sufficient (CV summary with generic skills)".
PARA_NOT_SUFFICIENT = """During my internship at UBS, I worked on financial analysis and prepared
presentations for clients. This experience strengthened my analytical and
communication skills and taught me the importance of teamwork."""

# Section 2, "Adds value (meaningful insight beyond the CV)".
PARA_ADDS_VALUE = """During my internship at UBS, I particularly enjoyed working on a project where
we had to make complex financial information accessible to clients. I realised
that I find the combination of analytical work and communicating ideas
particularly rewarding, which is one reason I am now interested in pursuing a
client-facing role."""

# Section 2, "CONTEXT-DEPENDENT EXAMPLE - same paragraph, different assessment
# depending on the CV".
PARA_DEPENDS = """During my internship at UBS, I applied analytical rigour and attention to detail
when benchmarking valuation multiples against industry peers, helping identify
relative mispricing and key valuation drivers. Presenting these findings to team
members and senior colleagues strengthened my ability to translate quantitative
analysis into clear, audience-specific insights."""


def _with_paragraph(paragraph: str) -> str:
    return "Dear Sir or Madam\n\n" + paragraph + "\n\nYours sincerely\nLena Bachmann\n"


def skills_removal_test() -> None:
    """
    v2, section 2: "Mentally remove generic statements such as 'this
    strengthened my teamwork/analytical/communication skills'. Does the
    remaining paragraph still communicate something substantive?"

    Their own worked example is the reason the cut runs from the claim to the
    end of the sentence rather than taking the whole sentence: "Presenting these
    findings to team members and senior colleagues strengthened my ability to
    translate quantitative analysis..." has to keep the presenting and lose the
    ability, because their analysis of that paragraph turns on the presenting.
    """
    kept, removed = cover_letter.skills_removed(
        "Presenting these findings to senior colleagues strengthened my ability to "
        "translate quantitative analysis into clear insights. I did this weekly.")
    problems = []
    if "Presenting these findings" not in kept:
        problems.append(f"substance was cut away: {kept!r}")
    if "strengthened my ability" in kept:
        problems.append(f"the claim survived: {kept!r}")
    if "I did this weekly" not in kept:
        problems.append(f"the cut ran past the end of the sentence: {kept!r}")
    if not removed or "strengthened my ability" not in removed[0]:
        problems.append(f"nothing was reported as removed: {removed}")
    check("the skills-removal cut takes the claim and leaves the substance", problems)

    # "...in St. Gallen." The cut must not stop at an abbreviation's full stop.
    kept, _ = cover_letter.skills_removed(
        "The role strengthened my ability to advise clients in St. Gallen and beyond. "
        "Next.")
    check("the cut does not stop at an abbreviation",
          [] if "St. Gallen" not in kept and "Next." in kept
          else [f"left: {kept!r}"])


def worked_examples_from_v2() -> None:
    """
    Career Services' own labels, reproduced by the measurements. The
    context-dependent paragraph is the real test: identical text, two CVs, two
    different answers, so nothing about the paragraph alone can produce them.
    """
    cases = [
        ("NOT sufficient", PARA_NOT_SUFFICIENT, CV_SAYS_LITTLE, True),
        ("NOT sufficient", PARA_NOT_SUFFICIENT, CV_SAYS_IT_ALL, True),
        ("adds value", PARA_ADDS_VALUE, CV_SAYS_LITTLE, False),
        ("adds value", PARA_ADDS_VALUE, CV_SAYS_IT_ALL, False),
    ]
    problems = []
    for label, paragraph, cv, should_flag in cases:
        facts = cover_letter.analyse(_with_paragraph(paragraph), "", "Analyst", cv,
                                     page_count=1)
        flagged = bool(facts["repetition_candidates"])
        if flagged != should_flag:
            problems.append(f"{label} against this CV: flagged={flagged}, "
                            f"expected {should_flag}")
    check("v2's worked examples get v2's own answers", problems)

    # The context-dependent one. Their labels are "Adds value IF the CV says
    # only ..." and "Limited added value IF the CV already says ...". The
    # measurement that has to separate them is the overlap after the cut.
    low = cover_letter.analyse(_with_paragraph(PARA_DEPENDS), "", "Analyst",
                               CV_SAYS_LITTLE, page_count=1)["paragraphs"][0]
    high = cover_letter.analyse(_with_paragraph(PARA_DEPENDS), "", "Analyst",
                                CV_SAYS_IT_ALL, page_count=1)["paragraphs"][0]
    key = "already_on_the_cv_after_the_skills_test"
    problems = []
    if high[key] <= low[key] * 2:
        problems.append(f"the same paragraph reads the same against both CVs: "
                        f"{low[key]} vs {high[key]}")
    if low[key] >= cover_letter.ECHO_SHARE:
        problems.append(f"a paragraph that adds value looks like a repeat: {low[key]}")
    check("the same paragraph is read against the CV, not on its own", problems)


def stemming_sees_the_same_work_twice() -> None:
    """
    Found here, not by a reviewer. A letter writes "internship",
    "presentations" and "benchmarking" where the CV wrote "Intern",
    "presented" and "benchmarked". On exact words not one of those pairs
    matched, so the most important check in the brief was reading a
    restatement of a CV bullet as entirely new material.
    """
    pairs = [("internship", "intern"), ("presentations", "presented"),
             ("benchmarking", "benchmarked"), ("valuation", "valuations"),
             ("Erfahrungen", "Erfahrung"), ("Fähigkeiten", "Fähigkeit")]
    problems = [f"{a} and {b} still look like different words"
                for a, b in pairs
                if cover_letter._stem(a.lower()) != cover_letter._stem(b.lower())]
    # And the noise list has to be stemmed with everything else, or "work" is
    # dropped as noise while "worked" comes through as the stem "work".
    if cover_letter._content_words("worked") & cover_letter._content_words("work"):
        problems.append("an inflected noise word survives the noise filter")
    check("an inflected word is not mistaken for a new one", problems)


def prior_contact_question() -> None:
    """
    v2, section 5: "Previous contact with the organisation: ALWAYS check whether
    contact is mentioned ... If not mentioned, ALWAYS ask: <their sentence>.
    This is a question, not a criticism."

    Their sentence, word for word. It is rendered in code for the same reason
    the disclaimer is: they wrote "ALWAYS", and a sentence the model composes is
    a sentence it can drop, reword, or decide a strong letter does not need.
    """
    theirs = ("Have you already spoken to someone at the organisation or attended one "
              "of their events? If so, consider mentioning this in your explanation of "
              "why the organisation interests you.")
    check("the question is Career Services' own, unaltered",
          [] if cover_letter.STRINGS["en"]["contact_question"] == theirs
          else [f"ours: {cover_letter.STRINGS['en']['contact_question']}"])

    silent = cover_letter.analyse(_with_paragraph(PARA_ADDS_VALUE), "", "Analyst",
                                  CV_SAYS_LITTLE, page_count=1)
    spoke = cover_letter.analyse(
        _with_paragraph("I spoke to two of your analysts at the careers fair in "
                        "St. Gallen, and what they said about the rotation is why I "
                        "am applying here rather than elsewhere."),
        "", "Analyst", CV_SAYS_LITTLE, page_count=1)
    rows_silent = cover_letter._measured_rows(silent, cover_letter.STRINGS["en"])
    rows_spoke = cover_letter._measured_rows(spoke, cover_letter.STRINGS["en"])
    problems = []
    if rows_silent["prior_contact"] != theirs:
        problems.append(f"not asked when no contact is mentioned: "
                        f"{rows_silent['prior_contact']}")
    if rows_spoke["prior_contact"] == theirs:
        problems.append("asked again of a student who already answered it")
    if "prior_contact" not in cover_letter.ESSENTIALS:
        problems.append("the row is not in the essentials table")
    check("the prior-contact question is always asked, and only once", problems)

    # "This is a question, not a criticism" - so the row must not read as a
    # fault, in either language.
    faults = ("missing", "no ", "not mentioned", "fehlt", "kein", "nicht genannt")
    problems = [f"{language}: the row reads as a shortcoming"
                for language, strings in cover_letter.STRINGS.items()
                if any(strings["contact_question"].lower().startswith(f)
                       for f in faults)]
    check("the prior-contact row is a question, not a shortcoming", problems)

    # And the model must not ask it as well, or the student is asked twice.
    messages = cover_letter.build_messages(
        _with_paragraph(PARA_ADDS_VALUE), "", "Analyst", silent, "English")
    brief = messages[-1]["content"]
    check("the model is told the question is already asked",
          [] if "Do not ask about earlier contact" in brief
          else ["the model is not told to leave the question alone"])


def paragraph_numbers_not_quotations() -> None:
    """
    The model answers with paragraph numbers, and the words the report prints
    are lifted from the letter here. Asked for a quotation a model paraphrases,
    and a paraphrase of the student's own paragraph printed back at them is the
    one thing the hard rules forbid.
    """
    letter = ("Dear Sir or Madam\n\n" + PARA_NOT_SUFFICIENT + "\n\n"
              + PARA_ADDS_VALUE + "\n\nYours sincerely\n")
    facts = cover_letter.analyse(letter, "", "Analyst", CV_SAYS_IT_ALL, page_count=1)
    numbers = [n["paragraph"] for n in facts["paragraphs"]]
    data = {"overall_assessment": "x", "essentials": {},
            "repetitive_paragraphs": [
                {"paragraph": numbers[0], "issue": "This repeats the CV."},
                {"paragraph": 99, "issue": "About a paragraph that does not exist."},
                {"paragraph": numbers[0], "opening": "A quotation I made up myself.",
                 "issue": "Second go at the same one."},
            ]}
    anchored = cover_letter._anchor_paragraphs(data, facts)
    kept = anchored["repetitive_paragraphs"]
    problems = []
    if any(f["paragraph"] == 99 for f in kept):
        problems.append("a paragraph number that does not exist was kept")
    if not kept:
        problems.append("a valid paragraph was dropped")
    for flagged in kept:
        if flagged["opening"] not in " ".join(letter.split()):
            problems.append(f"printed words that are not in the letter: "
                            f"{flagged['opening']!r}")
    check("a flagged paragraph is quoted from the letter, not from the model",
          problems)


def report_shows_the_filler_paragraph() -> None:
    """
    v2, section 7A: "Explicitly identify any substantive filler paragraph, even
    if the overall letter is strong." A strong overall assessment must not be
    able to swallow it.
    """
    letter = ("Dear Sir or Madam\n\n" + PARA_NOT_SUFFICIENT
              + "\n\nYours sincerely\n")
    facts = cover_letter.analyse(letter, "", "Analyst", CV_SAYS_IT_ALL, page_count=1)
    number = facts["paragraphs"][0]["paragraph"]
    data = cover_letter._anchor_paragraphs(
        {"overall_assessment": "A strong, well-targeted letter throughout.",
         "essentials": {k: "Fine." for k in
                        ["adds_value", "why_organisation", "why_role",
                         "what_you_bring", "conclusion"]},
         "repetitive_paragraphs": [
             {"paragraph": number,
              "issue": "It restates your UBS tasks and adds only skill claims."}]},
        facts)
    for language, strings in cover_letter.STRINGS.items():
        rendered = cover_letter.render_markdown(data, facts, strings)
        problems = []
        if strings["repetitive_heading"] not in rendered:
            problems.append("the flagged paragraph is not in the report")
        if "restates your UBS tasks" not in rendered:
            problems.append("the reason is not printed")
        if rendered.index(strings["repetitive_heading"]) > rendered.index(
                f"### 2. {strings['essentials']}"):
            problems.append("it is printed after the essentials table")
        check(f"a filler paragraph is named even on a strong letter ({language})",
              problems)

    # And nothing is printed when there is nothing to print: section 7B says
    # "Do not fill the report with generic praise or observations that add no
    # actionable value."
    clean = cover_letter.render_markdown(
        {"overall_assessment": "x", "essentials": {}, "repetitive_paragraphs": []},
        facts, cover_letter.STRINGS["en"])
    check("no empty filler section on a letter with no filler",
          [] if cover_letter.STRINGS["en"]["repetitive_heading"] not in clean
          else ["an empty heading is printed"])


def addressed_to_the_student() -> None:
    """
    Serena, round 6: the report should speak to the student, not about them.
    The rule is in the prompt; this is what happens when the prompt does not
    hold, which on the evidence of round 5 is a matter of when, not whether.
    """
    third_person = {
        "overall_assessment": "The candidate has written a clear letter.",
        "essentials": {"adds_value": "The candidate's motivation is explained."},
        "repetitive_paragraphs": [{"paragraph": 1, "opening": "x",
                                   "issue": "The applicant is repeating the CV."}]}
    problems = []
    if not cover_letter.THIRD_PERSON_RE.search(cover_letter._written_text(third_person)):
        problems.append("third-person writing is not detected at all")
    fixed = cover_letter._address_the_student(dict(third_person))
    written = cover_letter._written_text(fixed)
    for phrase in ("the candidate", "the applicant", "The candidate", "The applicant"):
        if phrase in written:
            problems.append(f"survived the fallback: {phrase}")
    if "You have written" not in written:
        problems.append(f"the verb was not carried with it: {written}")
    check("the report addresses the student, not a third party", problems)

    # The detector has to look everywhere the model writes prose, including the
    # field v2 added. A rule enforced in two of three places is not enforced.
    only_in_the_new_field = {"overall_assessment": "Clear.", "essentials": {},
                             "repetitive_paragraphs": [
                                 {"paragraph": 1, "opening": "x",
                                  "issue": "The candidate repeats the CV here."}]}
    check("third person is caught in the flagged-paragraph text too",
          [] if cover_letter.THIRD_PERSON_RE.search(
              cover_letter._written_text(only_in_the_new_field))
          else ["the new field is not checked"])


def scope_boundaries_are_in_the_prompt() -> None:
    """
    MP hardened this between rounds: in round 5 the USP suggestion was "do we
    want that?", and in round 6 "this shouldn't be provided by the tool!".
    Section 6 of v2 then listed it. There is no way to measure the absence of a
    suggestion in free prose, so what is pinned is that the instruction is
    still there - these are the rules that got weaker by being paraphrased.
    """
    prompt = cover_letter.SYSTEM_PROMPT.lower()
    required = {
        "no unique selling point": "unique selling point",
        "nothing to lead with or emphasise": "emphasise",
        "no judgement of persuasiveness": "persuasive",
        "no judgement of whether experience is strong enough": "strong enough",
        "no best-candidate verdict": "best candidate",
        "no rewriting": "never rewrite",
        "no template to fill in": "fill-in-the-blank",
        "no fixed four-paragraph structure": "four-paragraph",
        "no demand for a story": "dramatic story",
        "the skills-removal test": "skills-removal test",
        "per-paragraph assessment": "do not let strong motivation elsewhere",
        "direct address": 'as "you" and "your"',
        "no claim about an unseen cv": "claim no comparison",
    }
    check("every scope boundary in v2 is still in the prompt",
          [f"gone: {label}" for label, phrase in required.items()
           if phrase.lower() not in prompt])


def disclaimer_is_theirs() -> None:
    """Section 7A: "Always add" - followed by the sentence they wrote."""
    theirs = ("Please note that this is only a first feedback mainly about the "
              "structure and value-add of your Cover Letter. It does not evaluate the "
              "content in detail or how well you tailored the Cover Letter to the "
              "role. This you can discuss in your one-on-one session.")
    check("the disclaimer is Career Services' own, unaltered",
          [] if cover_letter.STRINGS["en"]["disclaimer"] == theirs
          else [f"ours: {cover_letter.STRINGS['en']['disclaimer']}"])

    facts = cover_letter.analyse(_with_paragraph(PARA_ADDS_VALUE), "", "Analyst", "",
                                 page_count=1)
    problems = []
    for language, strings in cover_letter.STRINGS.items():
        rendered = cover_letter.render_markdown(
            {"overall_assessment": "x", "essentials": {}}, facts, strings)
        if strings["disclaimer"] not in rendered:
            problems.append(f"{language}: not rendered")
        for key in cover_letter.ESSENTIALS:
            if strings["labels"][key] not in rendered:
                problems.append(f"{language}: row missing from the table: {key}")
    check("the disclaimer and all ten rows reach the report", problems)


def role_claims_cleaned_everywhere() -> None:
    """
    The round-5 enforcement has to cover the field v2 added as well. The
    original cleaned the assessment and the table and nothing else, because
    nothing else existed.
    """
    data = cover_letter._without_role_claims({
        "overall_assessment": "Fine.",
        "essentials": {"adds_value": "Fine."},
        "repetitive_paragraphs": [
            {"paragraph": 1, "opening": "x",
             "issue": "This adds nothing relevant to the position."}]})
    written = data["repetitive_paragraphs"][0]["issue"]
    check("a relevance claim is removed from a flagged paragraph too",
          [] if "relevant to the position" not in written else [f"survived: {written}"])


def only_the_body_is_a_paragraph() -> None:
    """
    Found on the first live run of v2, not in review. The model was handed the
    "Awesome Engineering Company" address block as substantive paragraph 1 and
    reported that it summarised the student's previous roles. An address block
    carries as many distinctive words as a short paragraph once a company name,
    a street and a town are in it, so length alone could never separate them.
    """
    letter = """Anna Gear
1234 Engineering Drive
Pittsburgh, PA 15213

September 30, 2024

Awesome Engineering Company
Attn: Hiring Manager
500 Industrial Parkway
Cleveland, OH 44101

Application for the Mechanical Engineering Internship

Dear Hiring Manager

""" + PARA_NOT_SUFFICIENT + """

Yours sincerely
Anna Gear
1234 Engineering Drive
Pittsburgh, PA 15213
"""
    facts = cover_letter.analyse(letter, "", "Mechanical Engineer", CV_SAYS_IT_ALL,
                                 page_count=1)
    offered = [note["opening"] for note in facts["paragraphs"]]
    problems = []
    for note in facts["paragraphs"]:
        for header in ("Engineering Drive", "Pittsburgh", "Awesome Engineering",
                       "Hiring Manager", "September 30", "Application for the"):
            if header in note["opening"]:
                problems.append(f"the letterhead is paragraph {note['paragraph']}: "
                                f"{note['opening'][:50]!r}")
                break
        if "Yours sincerely" in note["opening"]:
            problems.append(f"the sign-off is paragraph {note['paragraph']}")
    if not offered:
        problems.append("the real body paragraph was thrown out with the letterhead")
    check("only the body of the letter is assessed paragraph by paragraph", problems)

    # The salutation sharing a line with the body must not take the body with it.
    run_on = ("Dear Ms Keller, " + PARA_ADDS_VALUE
              + "\n\nYours sincerely\nLena Bachmann\n")
    facts = cover_letter.analyse(run_on, "", "Analyst", CV_SAYS_LITTLE, page_count=1)
    check("a salutation on the same line as the body does not hide it",
          [] if facts["paragraphs"] else ["the only paragraph was dropped"])


def no_claim_about_an_unseen_cv() -> None:
    """
    Found on the same live run. With no CV uploaded the model wrote that a
    paragraph "may closely mirror what is already on your CV" - hedged, but
    still a sentence about a document nobody here has seen. v2, section 2: "If
    no CV is available, do not claim to have verified overlap; instead say that
    passages read like a list of past experiences and may not add much beyond a
    CV." The thought is theirs and stays; what goes is the possessive.
    """
    data = cover_letter._without_cv_claims({
        "overall_assessment": "This may mirror what is already on your CV.",
        "essentials": {"adds_value": "Es steht schon in deinem Lebenslauf."},
        "repetitive_paragraphs": [
            {"paragraph": 1, "opening": "x", "issue": "Your CV already says this."}]})
    written = cover_letter._written_text(data)
    problems = [f"survived: '{claim}'" for claim in
                ("your CV", "Your CV", "deinem Lebenslauf")
                if claim in written]
    if "a CV" not in written:
        problems.append(f"the thought was deleted rather than generalised: {written}")
    check("with no CV uploaded, nothing is claimed about the student's CV", problems)

    # And the report's own heading over the flagged paragraphs asserted the
    # comparison too. The model was not the only one making the claim.
    facts = cover_letter.analyse(
        "Dear Sir or Madam\n\n" + PARA_NOT_SUFFICIENT + "\n\nYours sincerely\n",
        "", "Analyst", "", page_count=1)
    flagged = {"overall_assessment": "x", "essentials": {},
               "repetitive_paragraphs": [
                   {"paragraph": facts["paragraphs"][0]["paragraph"],
                    "opening": facts["paragraphs"][0]["opening"],
                    "issue": "It leans on skill claims."}]}
    problems = []
    for language, strings in cover_letter.STRINGS.items():
        rendered = cover_letter.render_markdown(flagged, facts, strings)
        if strings["repetitive_heading_no_cv"] not in rendered:
            problems.append(f"{language}: the no-CV heading is not used")
        if strings["repetitive_intro"] in rendered:
            problems.append(f"{language}: the report claims a comparison it never made")
    check("the report's own heading does not claim an unseen CV either", problems)


def paragraphs_without_blank_lines() -> None:
    """
    Career Services' own CMU sample is 456 words with not one blank line in it,
    so splitting on blank lines returned the whole letter as a single
    paragraph. Nothing went visibly wrong until v2 made the paragraph the unit
    of judgement, and then the report quoted the letterhead back at the student
    as a paragraph that repeated their CV.
    """
    letter = """Anna Gear
annagear@example.edu | (412)-555-1234
September 30, 20XX
Awesome Engineering Company
5678 Main Street
Pittsburgh, PA 15213
Dear Recruiting Manager,
I am writing to apply for the R & D Engineer position, which was shared with me
by a classmate at the university's STEM Career Fair. I am pursuing a master's
degree in Mechanical Engineering with an expected completion date of May 20XX,
and I believe my professional experience in product design fits what you do.
During my internship I worked on financial analysis and prepared presentations
for clients. This experience strengthened my analytical and communication
skills and taught me the importance of teamwork, which I would bring with me.
Best Regards,
Anna Gear
"""
    blocks = cover_letter._split_paragraphs(letter)
    body = cover_letter._body_paragraphs(blocks)
    problems = []
    if len(blocks) < 6:
        problems.append(f"a letter with no blank lines is still one block: {len(blocks)}")
    for number, paragraph in body:
        for header in ("Awesome Engineering", "Main Street", "Pittsburgh",
                       "September 30", "annagear", "Best Regards"):
            if header in paragraph:
                problems.append(f"paragraph {number} is letterhead or sign-off: "
                                f"{' '.join(paragraph.split())[:45]!r}")
                break
    if len(body) != 2:
        problems.append(f"expected the two body paragraphs, got {len(body)}: "
                        f"{[n for n, _ in body]}")
    check("paragraphs are recovered from a letter with no blank lines", problems)

    # And a letter that does use blank lines must not be re-split by geometry.
    normal = ("Dear Ms Keller\n\n" + PARA_ADDS_VALUE + "\n\n" + PARA_NOT_SUFFICIENT
              + "\n\nYours sincerely\nLena Bachmann\n")
    check("a letter with blank lines is split on them, not on line length",
          [] if len(cover_letter._split_paragraphs(normal)) == 4
          else [f"got {len(cover_letter._split_paragraphs(normal))} blocks"])


def prior_contact_means_this_organisation() -> None:
    """
    Found on the first live run. "...which was shared with me by Bob Smith at
    Carnegie Mellon University's STEM Career Fair" was read as contact with the
    employer, so the question was never asked - and the question is the whole
    point of the check. A careers fair is a place, not a contact.
    """
    cases = [
        # Not contact with this employer.
        ("shared with me by a classmate at the university's STEM Career Fair", False),
        ("I attended the careers fair in Zurich last autumn", False),
        ("I spoke to my professor about this role", False),
        ("Ich stehe gerne für ein Gespräch zur Verfügung", False),
        ("Ich habe mich im Rahmen meines Studiums mit der Branche beschäftigt", False),
        # Contact with this employer.
        ("I spoke to two of your analysts at the careers fair", True),
        ("After your company presentation at HSG I knew I wanted to apply", True),
        ("I attended one of your insight days last spring", True),
        ("I had a coffee chat with someone on the team last month", True),
        ("I met your team at the recruiting event", True),
        ("Nach Ihrer Firmenpräsentation an der HSG wusste ich es", True),
        ("Im Gespräch mit Ihrem Mitarbeiter habe ich erfahren", True),
        ("Ich habe mit Ihnen am Messestand gesprochen", True),
        ("Ich habe mit einem Ihrer Mitarbeitenden gesprochen", True),
    ]
    problems = [f"{'read as contact' if got else 'missed'}: {text!r}"
                for text, want in cases
                for got in [bool(cover_letter.PRIOR_CONTACT_RE.search(text))]
                if got != want]
    check("contact counts only when the letter points at this organisation", problems)


def german_signoff_with_an_eszett() -> None:
    """
    Found on the same run, and older than v2: CLOSING_RE was written as
    "gr[üu]e?ssen", so "Freundliche Grüße" never matched. The model was being
    told the sign-off was missing on a letter that had one, and it is the
    sign-off that tells the paragraph splitter where the body ends.
    """
    problems = [f"not recognised: {text}" for text in
                ("Freundliche Grüße", "Mit freundlichen Grüßen",
                 "Mit freundlichen Grüssen", "Mit freundlichen Gruessen",
                 "Herzliche Grüße", "Viele Grüße", "Yours sincerely")
                if not cover_letter.CLOSING_RE.search(text)]
    problems += [f"not recognised: {text}" for text in
                 ("Sehr geehrte Frau Müller", "Sehr geehrter Herr Keller",
                  "Dear Ms Keller", "Guten Tag")
                 if not cover_letter.SALUTATION_RE.search(text)]
    check("a sign-off spelled with an eszett is still a sign-off", problems)


def unreadable_layout_says_so() -> None:
    """
    A letter pasted into the box with its newlines stripped has neither blank
    lines nor line breaks, so there is nothing to find paragraph boundaries in.
    The failure mode to avoid is the one that started all of this: offering the
    whole document as "paragraph 1" and letting the model report that the
    letterhead repeats the CV. Saying nothing is also wrong - an unreadable
    layout has to be reported as unreadable, not as a letter with no paragraphs.
    """
    one_line = ("Anna Gear Pittsburgh PA 15213 Awesome Engineering Company Dear "
                "Hiring Manager I am applying for the role. "
                + "I worked on financial analysis and prepared presentations for "
                  "clients. " * 8
                + "Yours sincerely Anna Gear")
    facts = cover_letter.analyse(one_line, "", "Analyst", CV_SAYS_IT_ALL, page_count=1)
    brief = cover_letter._paragraph_brief(facts)
    problems = []
    if facts["paragraphs"]:
        problems.append(f"the whole letter is offered as a paragraph: "
                        f"{facts['paragraphs'][0]['opening'][:40]!r}")
    if not facts["paragraphs_unsplit"]:
        problems.append("the failure to split is not recorded")
    if "COULD NOT BE FOUND" not in brief:
        problems.append(f"the model is not told why there are no paragraphs: {brief[:70]}")
    check("a letter whose paragraphs cannot be found is reported as such", problems)

    # And a short letter is not an unreadable one: there is simply nothing in
    # it to assess, which is a fact about the letter and not about us.
    short = cover_letter.analyse("Dear Sir or Madam\n\nI would like the job.\n\n"
                                 "Yours sincerely\n", "", "Analyst", "", page_count=1)
    check("a short letter is not reported as unreadable",
          [] if not short["paragraphs_unsplit"]
          else ["a two-line letter is called unreadable"])



def the_claim_count_needs_every_claim() -> None:
    """
    A paragraph is only called repetitive when EVERY claim in it is known.

    The conservative direction on purpose: one new claim means the model has
    named something a recruiter would learn, and whether that is worth a
    paragraph is a judgement no counter should be making. The three parts
    checked here are the three ways the count can be wrong - too eager, blind
    to an invented claim, and blind to a generic skill claim counted as new.
    """
    letter = ("Dear Ms X\n\n"
              "I spent a month on the CSRD double-materiality assessment for my "
              "seminar paper and found the reconciliation harder than the model. "
              "This strengthened my analytical and communication skills.\n\n"
              "Yours sincerely\n")
    facts = cover_letter.analyse(letter, "", "Analyst", CV_SAYS_IT_ALL, page_count=1)
    note = facts["paragraphs"][0]
    number = note["paragraph"]

    def count(claims):
        copy = [dict(note)]
        cover_letter._count_the_claims(copy, {number: claims})
        return copy[0].get("claims"), copy[0].get("claims_already_on_the_cv")

    problems = []
    total, known = count([
        {"claim": "spent a month on the CSRD double materiality assessment",
         "already_on_the_cv": True},
        {"claim": "found the reconciliation harder than the model",
         "already_on_the_cv": False}])
    if (total, known) != (2, 1):
        problems.append(f"a paragraph with one new claim counted {known}/{total}")

    # An invented claim cannot tip a paragraph: it is not in it.
    total, known = count([
        {"claim": "spent a month on the CSRD double materiality assessment",
         "already_on_the_cv": True},
        {"claim": "found the reconciliation harder than the model",
         "already_on_the_cv": True},
        {"claim": "managed forty people in a Zurich warehouse",
         "already_on_the_cv": True}])
    if total != 2:
        problems.append(f"a claim that is not in the paragraph was counted: {total}")

    # Career Services' skills-removal test, applied per claim: a generic skill
    # claim is new to the CV and still carries nothing, so it is not counted as
    # the one new thing that saves a paragraph.
    total, known = count([
        {"claim": "spent a month on the CSRD double materiality assessment",
         "already_on_the_cv": True},
        {"claim": "found the reconciliation harder than the model",
         "already_on_the_cv": True},
        {"claim": "this strengthened my analytical and communication skills",
         "already_on_the_cv": False}])
    if (total, known) != (2, 2):
        problems.append(f"a generic skill claim counted as new information: "
                        f"{known}/{total}")
    # And the claim really is in the paragraph, so this sub-check is testing
    # the skills-removal test and not the anchor a second time.
    if "strengthened my analytical and communication skills" not in letter:
        problems.append("the skill claim is not in the paragraph it is filed under")
    check("a paragraph counts as repetitive only when every claim is known",
          problems)


def the_measured_repetition_is_reported() -> None:
    """
    A paragraph measured as asserting nothing new reaches the student.

    Measuring it and printing nothing is the round-7 complaint over again, one
    layer further in. The model is asked once more and, if it still leaves the
    paragraph out, the sentence is rendered here - because the finding is a
    measurement by then, not an opinion that can be declined.
    """
    facts = {"paragraphs": [{"paragraph": 2, "opening": "For almost a year I looked",
                             "full_text": "For almost a year I looked after the money."}],
             "nothing_new_paragraphs": [2]}
    stubborn = {"overall_assessment": "A strong letter throughout.",
                "essentials": {}, "repetitive_paragraphs": []}
    asked = []

    def refuse(*args, **kwargs):
        asked.append(1)
        return dict(stubborn)

    original = cover_letter._ask
    cover_letter._ask = refuse
    try:
        problems = []
        for code in ("en", "de"):
            out = cover_letter._enforce_the_comparison(
                object(), "m", [], dict(stubborn), facts, code)
            flagged = out.get("repetitive_paragraphs") or []
            if [f["paragraph"] for f in flagged] != [2]:
                problems.append(f"{code}: a measured repetition was not reported")
            elif not str(flagged[0].get("issue") or "").strip():
                problems.append(f"{code}: reported with no sentence to the student")
        if not asked:
            problems.append("the model was never asked to reconsider")

        # And the model's own sentence is kept when it does reconsider.
        cover_letter._ask = lambda *a, **k: {
            "overall_assessment": "One paragraph repeats.",
            "repetitive_paragraphs": [{"paragraph": 2, "issue": "The model's own."}]}
        out = cover_letter._enforce_the_comparison(
            object(), "m", [], dict(stubborn), facts, "en")
        kept = out.get("repetitive_paragraphs") or []
        if not kept:
            problems.append("the retry's finding was dropped")
        elif kept[0].get("issue") != "The model's own.":
            problems.append("the retry's own sentence was overwritten")

        # Nothing measured, nothing added, and no call made.
        def boom(*a, **k):
            raise AssertionError("asked with nothing measured")

        cover_letter._ask = boom
        out = cover_letter._enforce_the_comparison(
            object(), "m", [], dict(stubborn),
            {"paragraphs": [], "nothing_new_paragraphs": []}, "en")
        if out["repetitive_paragraphs"]:
            problems.append("a finding was invented with nothing measured")
    finally:
        cover_letter._ask = original
    check("a paragraph measured as adding nothing reaches the student", problems)


def adds_value_row_agrees_with_the_findings() -> None:
    """
    The row and the findings above it cannot contradict each other.

    A report flagged a paragraph as repeating the CV and then said, four lines
    below, that adding value beyond the CV was checked with nothing to flag.
    Both came out of the same answer: the model omits a row it considers fine,
    and the default filled it in without looking at what else it had said.
    """
    facts = cover_letter.analyse("Dear Ms X\n\nI did a thing.\n\nYours sincerely\n",
                                 "", "Analyst", "", page_count=1)
    problems = []
    for code, strings in cover_letter.STRINGS.items():
        flagged = cover_letter._essentials(
            {"repetitive_paragraphs": [{"paragraph": 1, "issue": "Repeats."}]},
            facts, strings)
        if flagged["adds_value"] == strings["nothing_to_flag"]:
            problems.append(f"{code}: all-clear printed above a repetition finding")
        clean = cover_letter._essentials({}, facts, strings)
        if clean["adds_value"] != strings["nothing_to_flag"]:
            problems.append(f"{code}: a clean letter does not read as clean")
        own = cover_letter._essentials(
            {"repetitive_paragraphs": [{"paragraph": 1}],
             "essentials": {"adds_value": "What the model said."}}, facts, strings)
        if own["adds_value"] != "What the model said.":
            problems.append(f"{code}: the model's own sentence was replaced")
    check("the adds-value row never contradicts the paragraphs above it", problems)



def the_conversation_is_given_both_documents() -> None:
    """
    In letter mode the chat is handed the letter AS a letter and the CV AS a CV.

    Round 7, and the complaint that started it: challenged on repetition, the
    bot answered that it did not have access to the CV and could not read it.
    It was right. The CV reached the measurements and stopped there, and the
    context block the conversation was given called the LETTER "CV (extracted,
    PII-stripped)" - one document under the other's name, and no CV at all. So
    the bot was asked about a document it had never been given, while holding a
    letter it had been told was that document.
    """
    letter = "Dear Ms X\n\nI would like to apply.\n\nYours sincerely\n"
    cv = "EDUCATION\n09/2023 - 06/2026 University of St. Gallen, BA Economics\n"
    block = prompts.build_context_block(
        letter, "", True, False, "en", "English", [], [],
        is_letter=True, letter_cv_text=cv)
    problems = []
    # The label immediately above each document. "CV (extracted" appears in
    # this block legitimately - it introduces the real CV - so what is checked
    # is which text follows which heading, not whether a phrase is present.
    if "Cover letter under review (extracted, PII-stripped):\n" + letter not in block:
        problems.append("the letter is not introduced as a cover letter")
    if "CV (extracted, PII-stripped):\n" + letter in block:
        problems.append("the cover letter is introduced as the CV")
    if cv not in block:
        problems.append("the CV is not in the context at all")
    if "You CAN read it" not in block:
        problems.append("nothing tells the model it has the CV")
    for forbidden in ("do not review it", "do not comment on its structure"):
        if forbidden not in block:
            problems.append(f"the CV is not marked reference-only: {forbidden!r}")

    # And with no CV, it must not be able to pretend otherwise.
    bare = prompts.build_context_block(
        letter, "", True, False, "en", "English", [], [], is_letter=True)
    if "not available" not in bare:
        problems.append("a missing CV is not reported as missing")
    if "Never claim or imply you have compared" not in bare:
        problems.append("nothing stops a comparison being claimed without a CV")

    # The CV path is untouched: there the uploaded document IS the CV.
    cv_mode = prompts.build_context_block(
        "EDUCATION\nHSG", "", True, False, "en", "English", [], [])
    if "CV (extracted" not in cv_mode:
        problems.append("CV mode no longer labels the CV as the CV")
    if "Cover letter" in cv_mode:
        problems.append("CV mode mentions a cover letter")
    check("the conversation is given both documents, each under its own name",
          problems)



def the_model_writes_no_em_dashes() -> None:
    """
    Career Services read them as machine-written, so the model's prose has none.

    The sweep has looked for this since round 5 and nothing enforced it: no
    prompt said so and no layer removed one. It passed three runs and then
    produced an em dash in two reports in a row, which is what a rule nobody
    implemented looks like from the outside.

    The report's OWN sentences keep theirs. "Checked — nothing to flag." is
    Career Services' wording, and so is every other row rendered in this file.
    """
    problems = []
    for before, after in (
            ("Your letter is strong — but one paragraph repeats the CV.",
             "Your letter is strong, but one paragraph repeats the CV."),
            ("It says what you did, not why — and that is the gap.",
             "It says what you did, not why, and that is the gap."),
            ("This is useful, — though optional.",
             "This is useful, though optional."),
            ("A dash at the end of a clause —.",
             "A dash at the end of a clause."),
    ):
        out = cover_letter._without_em_dashes(
            {"overall_assessment": before,
             "essentials": {"adds_value": before},
             "repetitive_paragraphs": [{"paragraph": 1, "issue": before}]})
        for where, got in (("overall", out["overall_assessment"]),
                           ("essentials", out["essentials"]["adds_value"]),
                           ("paragraph", out["repetitive_paragraphs"][0]["issue"])):
            if got != after:
                problems.append(f"{where}: {got!r} not {after!r}")

    # The words quoted from the letter are the student's and are left alone.
    quoted = {"repetitive_paragraphs": [
        {"paragraph": 1, "opening": "I worked at UBS — in Zurich", "issue": "Repeats."}]}
    if "—" not in cover_letter._without_em_dashes(quoted)[
            "repetitive_paragraphs"][0]["opening"]:
        problems.append("a dash the student wrote was edited out of the quotation")

    # And Career Services' own rendered sentences keep theirs.
    for code, strings in cover_letter.STRINGS.items():
        if "—" not in strings["nothing_to_flag"]:
            problems.append(f"{code}: the report's own wording lost its em dash")
    check("the model's prose carries no em dashes, and ours keep theirs", problems)



def a_paragraph_that_adds_something_is_not_called_repetition() -> None:
    """
    The measurement restrains the report in both directions, not just one.

    Putting the CV in the prompt cost something as well as buying something.
    Told to compare, the model began flagging paragraphs for overlapping with
    the CV at all: on the letter written to be strong it called the hospital
    paragraph a repetition, although that paragraph says the work was mostly
    cleaning inconsistent records and what that taught the student about Swiss
    hospital data, neither of which is on the CV. The measurement had it right,
    2 of 4 claims new, and a measurement that is only consulted when it agrees
    with the model is not being used.
    """
    def facts_for(known, total, singled_out=False):
        return {"paragraphs": [{"paragraph": 3, "opening": "I spent last summer",
                                "claims": total,
                                "claims_already_on_the_cv": known}],
                "repetition_candidates": ([{"paragraph": 3, "reason": "skill claims"}]
                                          if singled_out else []),
                "nothing_new_paragraphs": [3] if known == total else []}

    def flagged_after(known, total, **kw):
        data = {"repetitive_paragraphs": [{"paragraph": 3, "issue": "Repeats."}]}
        out = cover_letter._drop_overreported(data, facts_for(known, total, **kw))
        return [f["paragraph"] for f in out["repetitive_paragraphs"]]

    problems = []
    if flagged_after(2, 4):
        problems.append("half the claims new and still called a repetition")
    if flagged_after(1, 5):
        problems.append("four claims of five new and still called a repetition")
    if not flagged_after(3, 4):
        problems.append("a paragraph that mainly restates the CV was let through")
    if not flagged_after(4, 4):
        problems.append("a paragraph with nothing new was let through")
    # A paragraph the other measurements single out is a different fault, and
    # this layer has no business taking that finding away.
    if not flagged_after(1, 5, singled_out=True):
        problems.append("a skills-removal finding was dropped by the claim count")
    # And with nothing counted, nothing is second-guessed.
    data = {"repetitive_paragraphs": [{"paragraph": 3, "issue": "Repeats."}]}
    out = cover_letter._drop_overreported(
        data, {"paragraphs": [{"paragraph": 3, "opening": "x"}]})
    if not out["repetitive_paragraphs"]:
        problems.append("an unmeasured paragraph had its finding dropped")
    check("a paragraph with new claims in it is not called a repetition", problems)


def run() -> int:
    recipient_cases()
    author_signoff()
    facts_still_measurable()
    length_is_counted_not_guessed()
    very_short_still_caught()
    both_languages_complete()
    no_relevance_claim_without_an_advert()
    addresses_in_every_format()
    recipient_job_title_and_honorific()
    pdf_sections_in_order()
    section_five_picks()
    # Cover Letter Feedback Rules v2.
    skills_removal_test()
    worked_examples_from_v2()
    stemming_sees_the_same_work_twice()
    prior_contact_question()
    paragraph_numbers_not_quotations()
    report_shows_the_filler_paragraph()
    addressed_to_the_student()
    scope_boundaries_are_in_the_prompt()
    disclaimer_is_theirs()
    role_claims_cleaned_everywhere()
    only_the_body_is_a_paragraph()
    no_claim_about_an_unseen_cv()
    paragraphs_without_blank_lines()
    prior_contact_means_this_organisation()
    german_signoff_with_an_eszett()
    unreadable_layout_says_so()
    # Round 7: the CV is mandatory, and the comparison with it is measured.
    the_claim_count_needs_every_claim()
    the_measured_repetition_is_reported()
    adds_value_row_agrees_with_the_findings()
    the_conversation_is_given_both_documents()
    the_model_writes_no_em_dashes()
    a_paragraph_that_adds_something_is_not_called_repetition()
    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(run())
