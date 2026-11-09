"""
Cover letters written to order, each one aiming at a rule in Career Services'
v2 document, with what the report MUST and MUST NOT say written next to it.

The real samples cannot do this. They are whatever somebody happened to write,
so when a rule does not fire there is no way to tell whether the rule is broken
or the letter simply did not call for it. Here the answer is known before the
call is made: letter 1 contains their own "NOT sufficient" example almost
verbatim, so a build that does not flag it is broken, full stop.

Each case gives:
    letter    - what the student uploads
    jd        - the job advert, or "" for none
    role      - the target role the student typed, or ""
    must      - things the report has to contain or do
    must_not  - things it must never say
"""

CASES = []


def case(name, letter, must, must_not, jd="", role="", cv="", why=""):
    CASES.append({"name": name, "letter": letter.strip(), "jd": jd, "role": role,
                  "cv": cv, "must": must, "must_not": must_not, "why": why})


# --------------------------------------------------------------------------
# 1. v2 section 2: "Always flag a paragraph that mainly restates the CV...
#    Do not let strong motivation elsewhere cancel out a filler paragraph."
#    The middle paragraph is their own "NOT sufficient" example.
# --------------------------------------------------------------------------
case(
    "filler_paragraph_survives_strong_motivation",
    """
Lena Hofmann
Rosenbergstrasse 12
9000 St. Gallen

Zurich Insurance Group
Human Resources
Mythenquai 2
8002 Zurich

St. Gallen, 3 November 2026

Application for the Sustainability Analyst internship (ref. ZIG-2026-114)

Dear Ms Weber,

I am applying for the Sustainability Analyst internship because Zurich is one of the
few insurers publishing a transition plan with interim targets rather than a 2050
pledge alone, and I would like to learn how those targets survive contact with
underwriting decisions.

During my internship at UBS, I worked on financial analysis and prepared presentations
for clients. This experience strengthened my analytical and communication skills and
taught me the importance of teamwork.

What draws me to this particular role is the combination of quantitative work and
regulatory reading. In my seminar paper I spent a month on the CSRD double-materiality
rules and found I enjoyed the part most people avoid, which is reconciling a standard
with what a business actually measures.

I would be available from 1 February 2027. Thank you for considering my application,
and I would welcome the chance to discuss it with you.

Yours sincerely,
Lena Hofmann
""",
    must=["flags at least one repetitive paragraph"],
    must_not=["says the letter has no repetitive paragraphs"],
    why="their own NOT-sufficient example, surrounded by good motivation",
)

# --------------------------------------------------------------------------
# 2. v2 section 5: the prior-contact question is asked ALWAYS - unless contact
#    is already mentioned, in which case asking it is nonsense.
# --------------------------------------------------------------------------
case(
    "contact_already_mentioned_so_do_not_ask",
    """
Tobias Meier
Dufourstrasse 50
9000 St. Gallen

Stadler Rail AG
Ernst-Stadler-Strasse 1
9565 Bussnang

St. Gallen, 3 November 2026

Application for the Graduate Programme in Operations (ref. SR-GRAD-88)

Dear Mr Keller,

I spoke with two of your engineers at your company presentation at HSG Talents in
October, and what stayed with me was how concretely they described the trade-off
between build rate and customisation. That conversation is why I am applying.

My interest in the Graduate Programme comes from wanting to see that trade-off made
rather than described. I spent six months on a student project rescheduling a
component line, and the hardest part was not the model but persuading three teams to
agree on what counted as a delay.

I could start on 1 March 2027. Thank you for your time, and I would be glad to discuss
this further.

Kind regards,
Tobias Meier
""",
    must=["says contact was already mentioned"],
    must_not=["asks whether the student has spoken to anyone",
              "asks about events or a careers fair"],
    why="contact is stated plainly; asking the standard question would be absurd",
)

# --------------------------------------------------------------------------
# 3. v2 section 5: report only CLEAR gaps, and never claim to have checked
#    something the upload cannot show. No recipient, no advert, pasted text.
# --------------------------------------------------------------------------
case(
    "bare_letter_missing_the_formal_elements",
    """
Dear Sir or Madam,

I would like to apply for a position at your company. I am studying Business
Administration at the University of St. Gallen and I am interested in finance.

I am a hard-working and motivated person and I learn quickly.

Thank you for your consideration.

Best regards,
Sarah Brunner
""",
    must=["says the recipient or company block is missing",
          "says the start date is missing"],
    must_not=["claims the letter runs past one page",
              "claims to have checked a reference number"],
    why="nothing to measure length against, and genuinely missing elements",
)

# --------------------------------------------------------------------------
# 4. v2 section 3: a letter that only answers "what have I done?"
# --------------------------------------------------------------------------
case(
    "entirely_retrospective",
    """
Marc Baumgartner
Bahnhofstrasse 4
8001 Zurich

Helvetia Versicherungen
Dufourstrasse 40
9001 St. Gallen

Zurich, 3 November 2026

Application for the Junior Controller position

Dear Ms Frei,

I completed my Bachelor in Economics at the University of Zurich in 2024 with a grade
average of 5.2. During my studies I worked part-time at a logistics company where I
was responsible for invoice checking and supplier correspondence.

After graduating I spent eighteen months at an accounting firm in Winterthur. There I
prepared monthly closings for four clients and supported the year-end audit. I also
maintained the fixed-asset register and reconciled intercompany balances.

Before that I completed a commercial apprenticeship at a regional bank, where I rotated
through the payments, lending and back-office departments over three years.

Yours sincerely,
Marc Baumgartner
""",
    must=["notes the letter is mainly about the past"],
    must_not=["invents a motivation for the student"],
    why="no why-organisation, no why-role, no contribution, no future at all",
)

# --------------------------------------------------------------------------
# 5. THE GENERALISED ONE. Everything v2 asks for, done properly. The test is
#    that the report finds almost nothing - a build that manufactures findings
#    to fill the table fails here and nowhere else.
# --------------------------------------------------------------------------
case(
    "a_good_letter_leaves_little_to_say",
    """
Nina Castelli
Goethestrasse 18
9000 St. Gallen

Roche Diagnostics International AG
Forrenstrasse 2
6343 Rotkreuz

St. Gallen, 3 November 2026

Application for the Market Access Internship (ref. RDI-2026-402)

Dear Dr Lehmann,

Roche Diagnostics is the only company I have found whose market-access team publishes
its health-economic models openly, and reading the 2025 model for the cobas liat panel
is what made me want to apply. I disagreed with one of its assumptions about testing
in primary care, and I would like to work somewhere that lets me argue about it.

The internship appeals to me because it sits between evidence and reimbursement
negotiation. In my Bachelor thesis I built a cost-effectiveness model for point-of-care
testing in Swiss GP practices, and the part I underestimated was how little the
clinical evidence resolved: two equally defensible assumptions about repeat testing
changed the incremental cost per QALY by a factor of three. I learned more from
defending that choice to my supervisor than from building the model.

I spent last summer at the Kantonsspital in St. Gallen collecting utilisation data for
the diagnostics department. The work was mostly cleaning inconsistent records, which
taught me what a Swiss hospital dataset actually looks like before it reaches an
analyst. I would expect that to be useful here.

I am available from 1 July 2027 for six months. Thank you for considering my
application, and I would be glad to discuss it with you.

Yours sincerely,
Nina Castelli
""",
    must=["names the role or reference number as present",
          "says the recipient details are there",
          "says the start date is mentioned"],
    must_not=["flags a repetitive paragraph",
              "says the letter is mainly about the past",
              "suggests a unique selling point"],
    why="a strong letter; the risk here is invention, not detection",
)

# --------------------------------------------------------------------------
# 6. German, and the one place formal address keeps creeping back.
# --------------------------------------------------------------------------
case(
    "german_letter_is_addressed_informally",
    """
Jonas Brunner
Museumstrasse 7
9000 St. Gallen

Swisscom AG
Alte Tiefenaustrasse 6
3050 Bern

St. Gallen, 3. November 2026

Bewerbung um ein Praktikum im Bereich Datenanalyse (Ref. SC-2026-77)

Sehr geehrte Frau Baumann,

Swisscom interessiert mich, weil Sie als einziger Schweizer Anbieter die Auslastung
des Mobilfunknetzes als offene Daten veröffentlichen. Ich habe damit im Rahmen eines
Seminars gearbeitet und bin dabei auf eine Unstimmigkeit in den Nachtstunden
gestossen, die ich gerne einmal mit jemandem besprechen würde, der das Netz kennt.

Die Stelle reizt mich, weil sie Datenanalyse mit Infrastrukturfragen verbindet. In
meiner Seminararbeit habe ich ein Modell zur Vorhersage von Lastspitzen gebaut; der
schwierigste Teil war nicht das Modell, sondern zu entscheiden, welche Ausreisser
echte Ereignisse waren und welche Messfehler.

Ab dem 1. Februar 2027 wäre ich verfügbar. Für ein Gespräch stehe ich gerne zur
Verfügung und danke Ihnen für die Prüfung meiner Unterlagen.

Freundliche Grüsse
Jonas Brunner
""",
    must=["is written in German", "addresses the student with du"],
    must_not=["addresses the student with Sie or Ihr"],
    why="the du rule reached the CV prompt first and the letter prompt last",
)


# --- running them ----------------------------------------------------------

import os                                                           # noqa: E402
import re                                                           # noqa: E402
import sys                                                          # noqa: E402
import tomllib                                                      # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cover_letter                                                 # noqa: E402
import letter_pii                                                   # noqa: E402
from guardrails import language                                     # noqa: E402

MODEL = "gpt-4.1"
ASKS_CONTACT = re.compile(
    r"(spoken to someone|attended one of their events|coffee|careers? fair"
    r"|gesprochen|teilgenommen|Veranstaltung)", re.IGNORECASE)
FORMAL_DE = re.compile(
    r"\b[A-ZÄÖÜ][a-zäöüß]{2,}en\s+Sie\b"
    r"|(?<![.!?:]\s)(?<!^)(?<!\n)\bIhre?[nmrs]?\b"
    r"|\bIhre?[nmrs]?\s+(?:Lebenslauf|Anschreiben|Motivationsschreiben|Erfahrung)", re.M)
USP = re.compile(r"(unique selling|USP|Alleinstellungsmerkmal|what makes you unique"
                 r"|was dich einzigartig)", re.IGNORECASE)


def key():
    with open(".streamlit/secrets.toml", "rb") as handle:
        return tomllib.load(handle)["OPENAI_API_KEY"]


def check(case, data, facts, report, strings) -> list:
    """Every expectation, as a list of what went wrong."""
    wrong = []
    flagged = bool(data.get("repetitive_paragraphs"))
    written = cover_letter._written_text(data)
    lang = strings.get("lang", "en")

    for want in case["must"]:
        if want == "flags at least one repetitive paragraph" and not flagged:
            wrong.append("no repetitive paragraph flagged")
        if want == "says contact was already mentioned" and strings["contact_yes"] not in report:
            wrong.append("did not acknowledge the contact the letter mentions")
        if want == "says the recipient or company block is missing" \
                and strings["recipient_no"] not in report:
            wrong.append("missing recipient block not reported")
        if want == "says the start date is missing" \
                and strings["availability_no"] not in report:
            wrong.append("missing start date not reported")
        if want == "says the start date is mentioned" \
                and strings["availability_yes"] not in report:
            wrong.append("start date present but not recognised")
        if want == "says the recipient details are there" \
                and strings["recipient_yes"] not in report:
            wrong.append("recipient present but reported missing")
        if want == "names the role or reference number as present" \
                and strings["title_missing"] in report:
            wrong.append("role is named but reported missing")
        if want == "notes the letter is mainly about the past" and not data.get("retrospective"):
            wrong.append("wholly retrospective letter not marked retrospective")
        if want == "is written in German" and lang != "de":
            wrong.append(f"report language is {lang}, not de")
        if want == "addresses the student with du" and lang == "de" \
                and not re.search(r"\b(du|dein|deine|dir|dich)\b", report):
            wrong.append("German report never addresses the student with du")

    for never in case["must_not"]:
        if never == "says the letter has no repetitive paragraphs" and not flagged:
            pass                                  # covered by the must above
        if never == "asks whether the student has spoken to anyone" \
                and strings["contact_question"] in report:
            wrong.append("asked the contact question although contact is mentioned")
        if never == "asks about events or a careers fair" and ASKS_CONTACT.search(written):
            wrong.append(f"model asked about contact itself: "
                         f"{ASKS_CONTACT.search(written).group(0)!r}")
        if never == "claims the letter runs past one page" \
                and re.search(r"(runs? (past|over) one page|über eine Seite)", report, re.I):
            wrong.append("claimed it runs past one page with no page count")
        if never == "claims to have checked a reference number" \
                and strings["title_named"] in report:
            wrong.append("claimed the role was named with no advert and no role given")
        if never == "flags a repetitive paragraph" and flagged:
            wrong.append(f"invented a repetitive paragraph: "
                         f"{data['repetitive_paragraphs'][0].get('issue','')[:60]!r}")
        if never == "says the letter is mainly about the past" and data.get("retrospective"):
            wrong.append("called a forward-looking letter retrospective")
        if never == "suggests a unique selling point" and USP.search(written):
            wrong.append("suggested a unique selling point")
        if never == "addresses the student with Sie or Ihr" and lang == "de":
            hit = FORMAL_DE.findall(written)
            if hit:
                wrong.append(f"formal address in a German report: {sorted(set(hit))[:3]}")
        if never == "invents a motivation for the student" \
                and re.search(r"(you are motivated by|dich motiviert, weil)", written, re.I):
            wrong.append("invented a motivation")
    return wrong


def main() -> int:
    from openai import OpenAI
    client = OpenAI(api_key=key())
    bad = 0
    for case in CASES:
        raw = case["letter"]
        lang = language.detect_message_language(raw) or "en"
        sent = letter_pii.strip_letter_pii(raw, lang)["text"]
        facts = cover_letter.analyse(sent, case["jd"], case["role"], case["cv"],
                                     page_count=None)
        data = cover_letter.generate(client, MODEL, sent, case["jd"], case["role"],
                                     facts, language.SUPPORTED[lang])
        if not data:
            print(f"FAIL  {case['name']}: no report produced"); bad += 1; continue
        strings = cover_letter.STRINGS[lang]
        report = cover_letter.render_markdown(data, facts, strings)
        wrong = check(case, data, facts, report, strings)
        if wrong:
            bad += 1
            print(f"FAIL  {case['name']}  [{lang}]")
            for w in wrong:
                print(f"        {w}")
        else:
            print(f"ok    {case['name']:46} [{lang}]  {case['why']}")
    print(f"\n{len(CASES) - bad}/{len(CASES)} written-to-order letters behave as the rules require")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
