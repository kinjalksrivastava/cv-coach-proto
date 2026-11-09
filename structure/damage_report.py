"""
How wrong is the current parse, counted rather than asserted?

Three failures are visible by eye in inspect_current.py's output. This counts
them across the whole sample corpus, so the rebuild has a number to beat:

  1. HEADING SWALLOWED  - a heading the vocabulary does not know is absorbed
     into the section above it and parsed as if it were a job. The section it
     should have introduced does not exist, and every rule for it is skipped.
  2. ORPHANED TEXT      - lines belonging to no section at all. Nothing is
     measured about them and nothing in the report mentions them.
  3. SILENT SECTION     - a section with real content but zero parsed entries,
     so no entry-level rule runs and the section comes out Strong by default.

Offline, deterministic, no model.

    ./venv/bin/python structure/damage_report.py
"""

import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv_facts                                                   # noqa: E402
from extraction import extract_text                               # noqa: E402
from guardrails import headings as heading_lookup                 # noqa: E402

SAMPLES = os.path.expanduser("~/Downloads/CV Samples")

# A line that reads like a section heading: short, no date, and either written
# in capitals or one of the words CVs use for a section. Deliberately rough -
# this counts a symptom, it does not decide anything.
HEADING_WORDS = re.compile(
    r"\b(information|informationen|zusätzlich|additional|skills|kenntnisse|"
    r"sprachen|languages|interests|interessen|hobbies|engagement|activities|"
    r"aktivitäten|zertifikate|certificates|certifications|referenzen|"
    r"references|profil|profile|kompetenzen|competences|auszeichnungen|"
    r"awards|publikationen|publications|ehrenamt|volunteering)\b",
    re.IGNORECASE)


def looks_like_a_heading(text: str) -> bool:
    words = text.split()
    if not words or len(words) > 5:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    shouting = sum(c.isupper() for c in letters) / len(letters) > 0.8
    return bool(shouting or HEADING_WORDS.search(text))


def main() -> int:
    files = sorted(glob.glob(f"{SAMPLES}/**/*.pdf", recursive=True)
                   + glob.glob(f"{SAMPLES}/**/*.docx", recursive=True))
    swallowed, orphaned, silent = [], [], []
    orphan_lines = total_lines = 0

    for path in files:
        label = os.path.relpath(path, SAMPLES)
        with open(path, "rb") as handle:
            result = extract_text(handle.read(), os.path.basename(path))
        if not result.ok:
            print(f"ERROR {label}: {result.error}")
            continue
        text = result.text
        lines = text.splitlines()
        found = heading_lookup.find(text)
        sections = [{"heading": h["clean"], "category": h["category"],
                     "index": h["index"]} for h in found]
        sliced = cv_facts._split_sections(text, sections)

        claimed = set()
        for block in sliced:
            claimed.update(range(block["start"], block["end"]))
            entries = cv_facts._entries(block["lines"])
            for entry in entries:
                title = (entry["title_line"] or entry["line"]).strip()
                if looks_like_a_heading(title):
                    swallowed.append(f'{label}: "{title[:46]}" '
                                     f'inside {block["heading"]}')
            body = [l for l in block["lines"] if l.strip()]
            if body and not entries:
                silent.append(f'{label}: {block["heading"]} ({len(body)} lines)')

        live = [i for i, l in enumerate(lines) if l.strip()]
        loose = [i for i in live if i not in claimed]
        total_lines += len(live)
        orphan_lines += len(loose)
        if live and len(loose) / len(live) > 0.15:
            orphaned.append((label, len(loose), len(loose) / len(live)))

    print("=" * 78)
    print(f"PARSE DAMAGE over {len(files)} sample CVs")
    print("=" * 78)
    print(f"\n1. HEADINGS SWALLOWED AS JOBS  ({len(swallowed)})")
    for item in swallowed:
        print(f"     {item}")
    print(f"\n2. ORPHANED TEXT  ({orphan_lines} of {total_lines} lines = "
          f"{orphan_lines / total_lines:.0%} of all CV text is in no section)")
    print(f"   CVs losing more than 15%:  ({len(orphaned)})")
    for label, count, share in sorted(orphaned, key=lambda x: -x[2]):
        print(f"     {share:>4.0%}  {count:>3} lines   {label}")
    print(f"\n3. SECTIONS WITH CONTENT BUT NO PARSED ENTRIES  ({len(silent)})")
    for item in silent:
        print(f"     {item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
