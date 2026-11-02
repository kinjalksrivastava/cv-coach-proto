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
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI                                           # noqa: E402

import cover_letter                                                 # noqa: E402
import letter_pii                                                   # noqa: E402
from extraction import extract_text                                 # noqa: E402
from guardrails import language                                     # noqa: E402

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

# Names that appear in these letters and must never reach the model: the
# recipient, the author, and anyone they mention in passing.
FORBIDDEN = {
    "HSG Career Services template EN.pdf": ["Anika Muster", "Muster", "Martina Master"],
    "CMU sample EN (Anna Gear).txt": ["Anna Gear", "Gear", "annagear"],
    "FAU sample DE (Manuela Musterfrau).txt": ["Maria Muster", "Manuela Musterfrau"],
}

# Phrases that claim the letter fits the role, where no advert said what the
# role wants. MP, round 5.
CLAIMS_RELEVANCE = (
    "relevant for the role", "relevant to the role", "relevant for the position",
    "relevant to the position", "relevant for the trainee", "matches the requirements",
    "fits the requirements", "relevant für die stelle", "passend für die stelle",
    "entspricht den anforderungen",
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


def run_one(client, path: str) -> list[str]:
    name = os.path.basename(path)
    raw, pages = read(path)
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
    facts = cover_letter.analyse(sent, "", role, "", page_count=pages)
    strings = cover_letter.STRINGS[lang]
    data = cover_letter.generate(client, MODEL, sent, "", role, facts,
                                 language.SUPPORTED[lang])
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

    written = " ".join([str(data.get("overall_assessment", ""))]
                       + [str(v) for v in (data.get("essentials") or {}).values()])
    for claim in CLAIMS_RELEVANCE:
        if claim in written.lower():
            problems.append(f"relevance claimed with no advert: '{claim}'")
    if "—" in written:
        problems.append("an em dash in the model's own text")

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
        problems = run_one(client, path)
        failures += bool(problems)
        for problem in problems:
            print(f"        {problem}")
    print(f"\n{len(files) - failures}/{len(files)} letters clean")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
