"""
Old parser against new, on the same CVs, by the same measures.

The point of a rebuild is not that the new code is nicer. It is that the
failures the old one makes stop happening and no new ones appear. So both are
run over the same corpus and scored the same way, and the table is the thing
that decides whether the switch happens.

    ./venv/bin/python structure/compare.py
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
from structure.damage_report import looks_like_a_heading          # noqa: E402

SAMPLES = os.path.expanduser("~/Downloads/CV Samples")


def old(path: str) -> dict:
    with open(path, "rb") as handle:
        result = extract_text(handle.read(), os.path.basename(path))
    if not result.ok:
        return {}
    text = result.text
    live = [l for l in text.splitlines() if l.strip()]
    found = heading_lookup.find(text)
    sections = [{"heading": h["clean"], "category": h["category"], "index": h["index"]}
                for h in found]
    sliced = cv_facts._split_sections(text, sections)
    claimed, swallowed, entries, bullets, bare = set(), 0, 0, 0, 0
    for block in sliced:
        claimed.update(range(block["start"], block["end"]))
        for entry in cv_facts._entries(block["lines"]):
            entries += 1
            title = (entry["title_line"] or entry["line"]).strip()
            if looks_like_a_heading(title):
                swallowed += 1
            got = len([l for l in entry["bullets"] + entry["description"] if l.strip()])
            bullets += len([l for l in entry["bullets"] if l.strip()])
            if not got:
                bare += 1
    lines = text.splitlines()
    orphans = len([i for i, l in enumerate(lines)
                   if l.strip() and i not in claimed])
    return {"sections": len(sliced), "entries": entries, "bullets": bullets,
            "bare": bare, "swallowed": swallowed, "orphans": orphans,
            "lines": len(live)}


def new(path: str) -> dict:
    with open(path, "rb") as handle:
        doc = tree.build(layout.read_pdf(handle.read()))
    entries = [e for s in doc.sections for e in s.entries]
    swallowed = sum(1 for e in entries if looks_like_a_heading(e.title))
    placed = sum(1 for s in doc.sections
                 for _ in s.items) + sum(
        1 + len(e.bullets) + len(e.description) for e in entries)
    return {"sections": len(doc.sections), "entries": len(entries),
            "bullets": sum(len(e.bullets) for e in entries),
            "bare": sum(1 for e in entries if e.is_bare),
            "swallowed": swallowed, "orphans": 0, "lines": placed}


def main() -> int:
    files = sorted(glob.glob(f"{SAMPLES}/**/*.pdf", recursive=True))
    totals = {"old": {}, "new": {}}
    print(f'{"":<34} {"OLD  sec ent bul swal orph":<28} {"NEW  sec ent bul swal":<24}')
    print("-" * 88)
    for path in files:
        o, n = old(path), new(path)
        if not o:
            continue
        for key in ("sections", "entries", "bullets", "swallowed", "orphans", "bare"):
            totals["old"][key] = totals["old"].get(key, 0) + o[key]
            totals["new"][key] = totals["new"].get(key, 0) + n[key]
        flag = ""
        if n["entries"] > o["entries"]:
            flag = "  +entries"
        if o["swallowed"] and not n["swallowed"]:
            flag += "  -swallowed"
        print(f'{os.path.relpath(path, SAMPLES):<34} '
              f'{o["sections"]:>5}{o["entries"]:>5}{o["bullets"]:>5}'
              f'{o["swallowed"]:>5}{o["orphans"]:>6}      '
              f'{n["sections"]:>5}{n["entries"]:>5}{n["bullets"]:>5}'
              f'{n["swallowed"]:>5}{flag}')
    print("-" * 88)
    for key in ("sections", "entries", "bullets", "bare", "swallowed", "orphans"):
        print(f'  {key:<12} old {totals["old"][key]:>5}      new {totals["new"][key]:>5}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
