"""
How many bullets are actually on the page?

The rebuild claims the old parser saw 148 bullets where the new one sees 232.
That number proves nothing on its own: "the old one was blind to a third of
them" and "the new one is inventing a third of them" produce exactly the same
figure, and only one of them is good news.

So this counts them a third way, independently of both parsers. A bullet here
is a line that visually begins with a bullet marker - nothing about sections,
entries, indentation or any of the logic either parser uses. It is a dumb
count, which is the point: it cannot share their mistakes.

It undercounts on purpose in one case. A CV that indents its bullets without
printing any marker has bullets this will not see, so where the parsers report
MORE than this count, that is the reason to check rather than the conclusion
that they are wrong.

    ./venv/bin/python structure/bullet_audit.py
"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv_facts                                                   # noqa: E402
from extraction import extract_text                               # noqa: E402
from guardrails import headings as heading_lookup                 # noqa: E402
from structure import layout, tree                                # noqa: E402

SAMPLES = os.path.expanduser("~/Downloads/CV Samples")

# Deliberately wider than either parser's list. If a glyph is used as a marker
# anywhere in the corpus it belongs here, because the job of this file is to
# be the thing neither parser can hide behind.
MARKERS = "-–—•·*▪■●○◦‣→▸▹►⁃∙◆❖➢✓»▫◘□☐·"


def independent(path: str) -> int:
    """
    Rows that visibly start with a bullet marker. No other logic.

    "Visibly" has to include a marker this file has never heard of, because a
    Wingdings arrow arrives as whatever ASCII character the substituted font
    maps it to - a ">" on one CV. So a character opening three or more lines,
    always before a space and never a letter or digit, counts as a marker
    here too. It is still an independent count: it knows nothing about
    sections, entries or indentation, which is where both parsers can go
    wrong.
    """
    with open(path, "rb") as handle:
        pages = layout.read_pdf(handle.read())
    rows = [r for page in pages for r in layout.rows_of(page)]
    learned = tree.learn_markers(rows)
    total = 0
    for page in pages:
        for row in layout.rows_of(page):
            text = row.text.lstrip()
            if not text:
                continue
            if text[0] in (MARKERS + "".join(learned)) and text[1:2] in (" ", "\t"):
                total += 1
            elif text[:2] in ("o ", "O ") and text[2:3].isupper():
                total += 1
    return total


def old_count(path: str) -> int:
    with open(path, "rb") as handle:
        result = extract_text(handle.read(), os.path.basename(path))
    if not result.ok:
        return 0
    found = heading_lookup.find(result.text)
    sections = [{"heading": h["clean"], "category": h["category"], "index": h["index"]}
                for h in found]
    total = 0
    for block in cv_facts._split_sections(result.text, sections):
        for entry in cv_facts._entries(block["lines"]):
            total += len([l for l in entry["bullets"] if l.strip()])
    return total


def new_count(path: str) -> int:
    with open(path, "rb") as handle:
        doc = tree.build(layout.read_pdf(handle.read()))

    def walk(section) -> int:
        got = sum(len(e.bullets) for e in section.entries)
        for child in section.subsections:
            got += walk(child)
        return got
    return sum(walk(s) for s in doc.sections)


def main() -> int:
    files = sorted(glob.glob(f"{SAMPLES}/**/*.pdf", recursive=True))
    print(f'{"":<36} {"marked":>7} {"old":>6} {"new":>6}   verdict')
    print("-" * 78)
    totals = [0, 0, 0]
    for path in files:
        marked, old, new = independent(path), old_count(path), new_count(path)
        totals = [totals[0] + marked, totals[1] + old, totals[2] + new]
        verdict = ""
        if new > marked:
            verdict = f"new has {new - marked} more than are marked - CHECK"
        elif new < marked:
            verdict = f"new misses {marked - new}"
        if old < marked:
            verdict += f"  | old missed {marked - old}"
        print(f'{os.path.relpath(path, SAMPLES):<36} {marked:>7} {old:>6} {new:>6}   {verdict}')
    print("-" * 78)
    print(f'{"TOTAL":<36} {totals[0]:>7} {totals[1]:>6} {totals[2]:>6}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
