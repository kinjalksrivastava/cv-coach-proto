"""
Both parsers against the hand-written truth.

This is the only scoreboard in the project that is not self-referential. The
labels in ground_truth.py were read off the rendered pages by eye; neither
parser contributed to them. So when a number here goes up, it went up.

    ./venv/bin/python structure/score.py
    ./venv/bin/python structure/score.py --detail

Scored per CV, because a total hides a parser that is excellent on seven CVs
and useless on the eighth, and the eighth is somebody's application.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv_facts                                                   # noqa: E402
from extraction import extract_text                               # noqa: E402
from guardrails import headings as heading_lookup                 # noqa: E402
from structure import layout, tree                                # noqa: E402
from structure.ground_truth import TRUTH                          # noqa: E402

SAMPLES = os.path.expanduser("~/Downloads/CV Samples")


def expected(record: dict) -> dict:
    entry_sections = [b for _h, kind, b in record["sections"] if kind == "entries"]
    return {
        "sections": len(record["sections"]),
        "entries": sum(len(b) for b in entry_sections),
        "bullets": sum(sum(b) for b in entry_sections),
        "bare": sum(1 for b in entry_sections for n in b if n == 0),
    }


def from_old(path: str) -> dict:
    with open(path, "rb") as handle:
        result = extract_text(handle.read(), os.path.basename(path))
    if not result.ok:
        return {"sections": 0, "entries": 0, "bullets": 0, "bare": 0}
    found = heading_lookup.find(result.text)
    sections = [{"heading": h["clean"], "category": h["category"], "index": h["index"]}
                for h in found]
    sliced = cv_facts._split_sections(result.text, sections)
    entries = bullets = bare = 0
    for block in sliced:
        for entry in cv_facts._entries(block["lines"]):
            entries += 1
            got = len([l for l in entry["bullets"] if l.strip()])
            bullets += got
            if not got and not [l for l in entry["description"] if l.strip()]:
                bare += 1
    return {"sections": len(sliced), "entries": entries,
            "bullets": bullets, "bare": bare}


def from_new(path: str) -> dict:
    with open(path, "rb") as handle:
        doc = tree.build(layout.read_pdf(handle.read()))
    sections = entries = bullets = bare = 0

    def walk(section) -> None:
        """Count this section AND everything nested inside it.

        The first version returned early when a section had subsections, so a
        parent heading's own entries were never counted at all: exp cv bad 1
        scored 0 entries against a truth of 12, and the tree was marked wrong
        for nesting sub-headings under a parent that genuinely exists in the
        document. That one bug made the parser look 10 errors worse than it is.
        """
        nonlocal sections, entries, bullets, bare
        for child in section.subsections:
            walk(child)
        # A heading that exists only to group sub-headings is not itself a
        # section in the hand labelling, which flattens them - but its own
        # entries are real and must be counted either way. Returning early,
        # as the first version did, dropped them: exp cv bad 1 scored 0
        # entries against a truth of 12.
        if not section.subsections:
            sections += 1
        for entry in section.entries:
            entries += 1
            bullets += len(entry.bullets)
            if entry.is_bare:
                bare += 1

    for section in doc.sections:
        walk(section)
    return {"sections": sections, "entries": entries,
            "bullets": bullets, "bare": bare}


def error(got: dict, want: dict) -> int:
    return sum(abs(got[k] - want[k]) for k in ("sections", "entries", "bullets"))


def main() -> int:
    old_total = new_total = 0
    rows = []
    for name, record in TRUTH.items():
        path = os.path.join(SAMPLES, name)
        if not os.path.exists(path):
            print(f"missing: {name}")
            continue
        want, old, new = expected(record), from_old(path), from_new(path)
        eo, en = error(old, want), error(new, want)
        old_total += eo
        new_total += en
        rows.append((name, want, old, new, eo, en))

    print(f'{"":<34} {"truth":>18} {"old":>18} {"new":>18}   err')
    print(f'{"":<34} {"sec ent bul bare":>18} {"sec ent bul bare":>18} '
          f'{"sec ent bul bare":>18}  old new')
    print("-" * 100)
    for name, want, old, new, eo, en in rows:
        mark = "  <<" if en < eo else ("  !!" if en > eo else "")
        print(f'{os.path.basename(name):<34} '
              f'{want["sections"]:>4}{want["entries"]:>4}{want["bullets"]:>5}'
              f'{want["bare"]:>5} '
              f'{old["sections"]:>4}{old["entries"]:>4}{old["bullets"]:>5}'
              f'{old["bare"]:>5} '
              f'{new["sections"]:>4}{new["entries"]:>4}{new["bullets"]:>5}'
              f'{new["bare"]:>5} '
              f'{eo:>4}{en:>4}{mark}')
    print("-" * 100)
    print(f'{"TOTAL ABSOLUTE ERROR":<34} {"":>18} {"":>18} {"":>18} '
          f'{old_total:>4}{new_total:>4}')
    print()
    if new_total < old_total:
        print(f"The new parser is closer to the truth: {new_total} against "
              f"{old_total}, {old_total - new_total} fewer errors.")
    elif new_total > old_total:
        print(f"The new parser is WORSE: {new_total} against {old_total}.")
    else:
        print("The two are level.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
