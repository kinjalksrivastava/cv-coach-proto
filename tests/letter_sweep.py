"""
Real cover letters, through the real pipeline, with the real model.

tests/cover_letters.py runs offline and pins the letter rules. This one is the
opposite: it strips, measures, calls the model, renders the report and the PDF,
and then reads the report back looking for what Career Services reported in
round 5. Slow, and it costs money.

    ./venv/bin/python tests/letter_sweep.py

The samples live outside the repository, beside the CV ones, because they are
other people's documents:

    ~/Downloads/Cover Letter Samples/

Currently Career Services' own template, a Carnegie Mellon sample and a German
sample from FAU Erlangen. A .pdf or .docx is treated as an upload, so the page
count is read from the file; a .txt stands for text pasted into the box, where
there is no file and no page count to read.
"""

import glob
import re
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI                                           # noqa: E402

import cover_letter                                                 # noqa: E402
import letter_cv_review                                             # noqa: E402
import letter_pii                                                   # noqa: E402
from extraction import extract_text                                 # noqa: E402
from guardrails import language                                     # noqa: E402
from pii import strip_pii                                           # noqa: E402

REVIEWS_THE_CV = re.compile(
    # The verb has to follow the CV directly. Reaching 80 characters ahead for
    # it matched "repeats what is already on your CV, and does not add anything
    # new", which is feedback on the LETTER and exactly what this report is for.
    r"\b(?:your|dein(?:em|en|er)?)\s+(?:CV|résumé|resume|Lebenslauf)\s+"
    r"(?:\w+\s+){0,2}?"
    r"\b(?:should|could|needs?|lacks?|is\s+missing|expand|restructure|reorder|"
    r"sollte[st]?|könntest|müsste[st]?|fehlt|fehlen)\b"
    r"|\b(?:add|adding|include|including|mention|mentioning|put|list|listing|"
    r"ergänz\w*|aufnehmen|hinzufüg\w*)\b[^.!?]{0,60}?\b(?:to|in|into|auf|in)\s+"
    r"(?:your|dein(?:en|em)?|the)\s+(?:CV|résumé|resume|Lebenslauf)\b", re.IGNORECASE)

SAMPLES = os.path.expanduser("~/Downloads/Cover Letter Samples")
MODEL = "gpt-4.1"

# The role each letter is written for, as a student would type it into the box.
# No job advert for any of them: that is the case round 5 complained about, and
# the one the report must not claim relevance in.
ROLES = {
    "HSG Career Services template EN.pdf": "Graduate Business Innovation",
    "CMU sample EN (Anna Gear).txt": "R & D Engineer",
    "FAU sample DE (Manuela Musterfrau).txt": "Praktikum Logistik",
}

# The CV each letter is uploaded with, since round 7 made it mandatory. Only
# the three documents that are actually written letters get one: the other four
# are templates and guides, and a CV for "Abschnitt 2: Ihre aktuelle Tätigkeit"
# would be inventing a student to go with a form. Those four keep testing the
# path where no CV is available, which the code still has to handle - a CV that
# cannot be read stops the upload, but generate() is called from here too.
#
# Each one lists what its letter says the student did, in the form a CV uses:
# entries and bullets, what they did and when, and nothing about why. That is
# the point of the comparison. A letter whose paragraphs only retell those
# bullets adds nothing; a letter that says why it chose them, what went wrong
# or what it learned does, and both kinds are below on purpose.
CVS = {
    # Written strong, and the guard against the comparison learning to punish
    # any mention of the CV: the thesis and the partnerships role are both on
    # it, and the letter uses them to say something else.
    "HSG Career Services template EN.pdf": """
EDUCATION
09/2022 - 06/2024   University of St. Gallen, MA in Business Innovation
  Master thesis: an AI-powered recommendation system
09/2018 - 06/2021   University of St. Gallen, BA in Business Administration

EXTRACURRICULAR
09/2022 - present   Head of Partnerships, Fashion Society HSG
  Approached and signed partner companies for the society's events

INTERESTS
Rock climbing (10 years), technology, languages
""",
    # The opposite case, and a real one: the body paragraphs walk through the
    # NEI work the CV already lists, role by role.
    "CMU sample EN (Anna Gear).txt": """
EDUCATION
08/20XX - 05/20XX   Carnegie Mellon University, MS in Mechanical Engineering
  Research project on design and development of mechanical systems

WORK EXPERIENCE
20XX - 20XX   Product Research and Development, National Engineering, Inc.
  Designed and developed two new one-way clutch technologies for the
  two-wheeler industry
  Lead engineer for a new seal mechanism with zero grease leakage and longer
  running life
  Collaborated with the product design team on improving thrust load carrying
  capacity for a ball bearing and on a large radial-axial load carrying bearing
  design, both submitted for patents at the Indian Patent Office

SKILLS
CAD, FEA, project management
""",
    "FAU sample DE (Manuela Musterfrau).txt": """
AUSBILDUNG
10/2018 - heute   Universität Erlangen-Nürnberg, BSc Wirtschaftswissenschaften
  Kurse in Logistik und Beschaffung
  Mitarbeit in studentischen Projektgruppen

BERUFSERFAHRUNG
09/2017 - 08/2018   Freiwilliges Jahr, Stadtgärtnerei
  Pflege der Grünanlage
  Führungen in der Grünanlage

KENNTNISSE
MS Office, Deutsch (Muttersprache), Englisch (B2)
""",
}

# Names that appear in these letters and must never reach the model: the
# recipient, the author, and anyone they mention in passing.
FORBIDDEN = {
    "HSG Career Services template EN.pdf": ["Anika Muster", "Muster", "Martina Master"],
    "CMU sample EN (Anna Gear).txt": ["Anna Gear", "Gear", "annagear"],
    "FAU sample DE (Manuela Musterfrau).txt": ["Maria Muster", "Manuela Musterfrau"],
}

# Phrases that claim the letter fits the role, where no advert said what the
# role wants. MP, round 5.
# Anything that claims to know what the advert asked for, when no advert was
# uploaded. Miriam, round 6: "When the person doesn't upload a job description
# then the bot should not say: 'relevant for the role'." The sweep ran green on
# the adjective "relevant" alone while the model wrote "the skills and mindset
# NEEDED for the position" on Career Services' own template - the same claim,
# one synonym away, which is why this list now covers the synonyms too.
CLAIMS_RELEVANCE = (
    "relevant for the role", "relevant to the role", "relevant for the position",
    "relevant to the position", "relevant for the trainee", "matches the requirements",
    "fits the requirements", "relevant für die stelle", "passend für die stelle",
    "entspricht den anforderungen",
    "needed for the role", "needed for the position", "required for the role",
    "required for the position", "required for the job", "necessary for the role",
    "expected for the role", "sought for the role", "relevant skills",
    "what the role requires", "what the position requires", "what the job requires",
    "what the role needs", "what the employer is looking for",
    "the role is looking for", "the position is looking for",
    "für die stelle benötigt", "für die position erforderlich",
    "relevante fähigkeiten", "relevanten fähigkeiten", "relevante kompetenzen",
)


def key() -> str:
    with open(".streamlit/secrets.toml", "rb") as handle:
        return tomllib.load(handle)["OPENAI_API_KEY"]


def read(path: str) -> tuple[str, int | None]:
    """Returns (text, page_count). A .txt is pasted text: no file, no pages."""
    if path.endswith(".txt"):
        with open(path, encoding="utf-8") as handle:
            return handle.read(), None
    with open(path, "rb") as handle:
        result = extract_text(handle.read(), os.path.basename(path))
    if not result.ok:
        raise RuntimeError(result.error)
    return result.text, result.meta.get("page_count")


class Unusable(Exception):
    """The file cannot be read at all - which the app tells the student."""


def run_one(client, path: str) -> list[str]:
    name = os.path.basename(path)
    try:
        raw, pages = read(path)
    except RuntimeError as refusal:
        # An image-only PDF with no text layer. app.py shows this message and
        # stops, which is the right answer and not a failure of the letter
        # rules - so the sweep records it and moves on rather than dying on it.
        # What matters is that the refusal names the cause and tells the
        # student what to do.
        message = str(refusal)
        if not ("scanned" in message or "image" in message):
            return [f"unreadable file refused without saying why: {message[:70]}"]
        raise Unusable(message) from refusal
    lang = language.detect_message_language(raw) or "en"
    cleaned = letter_pii.strip_letter_pii(raw, lang)
    sent = cleaned["text"]

    problems = []
    for forbidden in FORBIDDEN.get(name, []):
        if forbidden.lower() in sent.lower():
            problems.append(f"'{forbidden}' was about to be sent to the model")
    if cleaned["residual"]:
        problems.append(f"residual personal data: {cleaned['residual']}")

    role = ROLES.get(name, "")
    # The CV goes through the same redaction as the letter, as it does in the app.
    cv = strip_pii(CVS[name], lang)["text"] if name in CVS else ""
    facts = cover_letter.analyse(
        sent, "", role, cv, page_count=pages,
        compare=lambda paragraphs: letter_cv_review.read(client, MODEL,
                                                         paragraphs, cv))
    strings = cover_letter.STRINGS[lang]
    data = cover_letter.generate(client, MODEL, sent, "", role, facts,
                                 language.SUPPORTED[lang], cv_text=cv)
    if not data:
        return problems + ["the model returned nothing"]

    markdown = cover_letter.render_markdown(data, facts, strings)
    blob = cover_letter.to_pdf(data, facts, strings)

    for forbidden in FORBIDDEN.get(name, []):
        if forbidden.lower() in markdown.lower():
            problems.append(f"'{forbidden}' is printed in the report")

    length_row = cover_letter._measured_rows(facts, strings)["length"]
    if pages == 1 and ("runs to" in length_row or "umfasst 1 Seiten" in length_row):
        problems.append(f"a one-page letter is said to run over: {length_row}")
    if pages is None and "could not be measured" not in length_row \
            and "nicht messen" not in length_row:
        problems.append(f"length claimed without a page count: {length_row}")

    # Everything the model itself wrote, the field v2 added included. The
    # checks below were passing on two thirds of the output once
    # 'repetitive_paragraphs' existed and nothing gathered it up.
    written = cover_letter._written_text(data)
    for claim in CLAIMS_RELEVANCE:
        if claim in written.lower():
            problems.append(f"relevance claimed with no advert: '{claim}'")
    if "—" in written:
        problems.append("an em dash in the model's own text")

    # Du, never Sie - the same rule the CV report follows, and the same reason:
    # Career Services address students informally, and every sentence this
    # report renders itself does. The CV prompt was fixed first and the letter
    # prompt was missed, so German letter reports read "warum Sie sich
    # bewerben" one row above "ab wann du könntest".
    if lang == "de":
        formal = re.findall(
            r"\b[A-ZÄÖÜ][a-zäöüß]{2,}en\s+Sie\b"
            r"|(?<![.!?:]\s)(?<!^)(?<!\n)\bIhre?[nmrs]?\b"
            r"|\bIhre?[nmrs]?\s+(?:Lebenslauf|CV|Bewerbung|Motivationsschreiben"
            r"|Erfahrung|Qualifikation|Motivation|Schreiben|Anschreiben)",
            written, re.M)
        if formal:
            problems.append(f"formal address in a German letter report: "
                            f"{sorted(set(formal))[:3]} - this report uses du")

    # --- Cover Letter Feedback Rules v2 ---
    #
    # v2, section 5: the prior-contact question is asked ALWAYS, and the report
    # renders Career Services' own sentence. Twice is as wrong as never: if the
    # model asks as well, the student reads the same question in two places.
    question = strings["contact_question"]
    asked = markdown.count(question[:60])
    if not facts["mentions_prior_contact"] and asked != 1:
        problems.append(f"the prior-contact question appears {asked} times")
    if facts["mentions_prior_contact"] and asked:
        problems.append("asked about contact the letter already mentions")
    for echo in ("coffee chat", "careers fair", "career fair", "kaffeegespräch",
                 "karrieremesse", "firmenpräsentation"):
        if echo in written.lower():
            problems.append(f"the model asked about contact as well: '{echo}'")

    # Serena, round 6: write to the student, not about them.
    third = cover_letter.THIRD_PERSON_RE.search(written)
    if third:
        problems.append(f"the student is written about in the third person: "
                        f"'{third.group(0)}'")

    # An internal label, so a value outside the three is a sign the model has
    # drifted from the brief rather than something the student would see.
    if data.get("added_value") is None:
        problems.append("no added-value category was returned")

    # Where no CV came with the letter - the templates and guides - every one of
    # these would be a claim about a document the model has never seen. v2,
    # section 2: "If no CV is available, do not claim to have verified overlap."
    if not cv:
        for claim in ("your cv already", "already on your cv", "repeats your cv",
                      "steht schon in deinem lebenslauf", "wiederholt deinen lebenslauf",
                      "bereits in deinem lebenslauf"):
            if claim in written.lower() or claim in markdown.lower():
                problems.append(f"claimed an overlap with a CV it never saw: '{claim}'")

    # With a CV, the thing to check is the other way round: a paragraph measured
    # as asserting nothing the CV does not already carry has to reach the
    # student. That reading is the answer to Career Services' most important
    # question, and a report that measures it and prints nothing is the round-7
    # complaint over again.
    printed = {f["paragraph"] for f in (data.get("repetitive_paragraphs") or [])}
    unsaid = [n for n in (facts.get("nothing_new_paragraphs") or []) if n not in printed]
    if unsaid:
        problems.append(f"paragraphs {unsaid} assert nothing the CV lacks and are "
                        "not reported")

    # And it must stay a letter report. The CV is in the prompt to be compared
    # against, not reviewed: nothing in this report has anywhere to put CV
    # feedback, and the student did not ask for it.
    cv_advice = REVIEWS_THE_CV.search(written)
    if cv and cv_advice:
        problems.append(f"gave feedback on the CV: {cv_advice.group(0)[:70]!r}")

    # The words the report quotes come from the letter, never from the model.
    for flagged in data.get("repetitive_paragraphs") or []:
        if flagged["opening"] not in " ".join(sent.split()):
            problems.append(f"quoted words that are not in the letter: "
                            f"{flagged['opening'][:40]!r}")

    if not blob:
        problems.append("no PDF was produced")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "letter_reports")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, name + ".md"), "w", encoding="utf-8") as handle:
        handle.write(markdown)

    print(f"{'ok   ' if not problems else 'FAIL '} {name:<46} {lang}  "
          f"pages={pages}  words={facts['word_count']}  "
          f"redacted={len(cleaned['redactions'])}")
    return problems


def main() -> int:
    files = sorted(glob.glob(f"{SAMPLES}/*.pdf") + glob.glob(f"{SAMPLES}/*.docx")
                   + glob.glob(f"{SAMPLES}/*.txt"))
    if not files:
        print(f"No samples in {SAMPLES}")
        return 1
    client = OpenAI(api_key=key())
    failures = 0
    for path in files:
        try:
            problems = run_one(client, path)
        except Unusable as refusal:
            print(f"ok    {os.path.basename(path)[:44]:46} refused cleanly: "
                  f"{str(refusal)[:52]}...")
            continue
        failures += bool(problems)
        for problem in problems:
            print(f"        {problem}")
    print(f"\n{len(files) - failures}/{len(files)} letters clean")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
