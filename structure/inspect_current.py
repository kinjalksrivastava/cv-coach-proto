"""
What does the bot actually think a CV looks like?

Nobody has ever looked. We have only ever read the report that comes out of
the far end, and every parsing bug this round - a bullet glyph that was not on
a list, a German heading that was not in a vocabulary, a section filed as
"Other" and therefore never checked - would have been visible in seconds here.

This prints the tree the CURRENT pipeline builds, for every sample CV, so it
can be read against the real document:

    section
      entry
        how many bullets, or BARE

Offline and deterministic: heading vocabulary only, no model, no network. That
is deliberate. The model is the layer that rescues a heading the vocabulary
misses, and what we need to see first is how much rescuing it is being asked
to do - because when it gets that wrong, the section is skipped silently.

    ./venv/bin/python structure/inspect_current.py
    ./venv/bin/python structure/inspect_current.py --quiet   # summary only
"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv_facts                                                   # noqa: E402
from extraction import extract_text                               # noqa: E402
from guardrails import headings as heading_lookup                 # noqa: E402

SAMPLES = os.path.expanduser("~/Downloads/CV Samples")


def tree(path: str) -> dict:
    with open(path, "rb") as handle:
        result = extract_text(handle.read(), os.path.basename(path))
    if not result.ok:
        return {"error": result.error}

    text = result.text
    lines = text.splitlines()

    # Every heading the vocabulary can find on its own, as detect_sections
    # would hand them over before the model is consulted.
    found = heading_lookup.find(text) if hasattr(heading_lookup, "find") else []
    sections = [{"heading": h["clean"], "category": h["category"], "index": h["index"]}
                for h in found]
    sliced = cv_facts._split_sections(text, sections)

    claimed = set()
    out = []
    for block in sliced:
        entries = cv_facts._entries(block["lines"])
        for position in range(block["start"], block["end"]):
            claimed.add(position)
        out.append({
            "heading": block["heading"],
            "category": block["category"],
            "entries": [{
                "title": (e["title_line"] or e["line"]).strip()[:64],
                "bullets": len([l for l in e["bullets"] if l.strip()]),
                "description": len([l for l in e["description"] if l.strip()]),
            } for e in entries],
            "body_lines": len([l for l in block["lines"] if l.strip()]),
        })

    orphans = [lines[i].strip() for i in range(len(lines))
               if i not in claimed and lines[i].strip()]
    total_bullets = sum(1 for l in lines if cv_facts._is_bullet(l))
    return {"sections": out, "orphans": orphans, "total_bullets": total_bullets,
            "line_count": len([l for l in lines if l.strip()]),
            "source": result.meta.get("source")}


def main() -> int:
    quiet = "--quiet" in sys.argv
    files = sorted(glob.glob(f"{SAMPLES}/**/*.pdf", recursive=True)
                   + glob.glob(f"{SAMPLES}/**/*.docx", recursive=True))
    if not files:
        print(f"No samples in {SAMPLES}")
        return 1

    no_sections, bare_sections, orphan_heavy = [], [], []
    for path in files:
        label = os.path.relpath(path, SAMPLES)
        data = tree(path)
        if "error" in data:
            print(f"ERROR {label}: {data['error']}")
            continue

        orphan_share = (len(data["orphans"]) / data["line_count"]
                        if data["line_count"] else 0)
        if not data["sections"]:
            no_sections.append(label)
        if orphan_share > 0.4:
            orphan_heavy.append((label, orphan_share))

        if not quiet:
            print("=" * 78)
            print(f"{label}   [{data['source']}]  {data['line_count']} lines, "
                  f"{data['total_bullets']} bullets")
            print("=" * 78)
        for section in data["sections"]:
            if not section["entries"]:
                bare_sections.append(f'{label}: {section["heading"]}')
            if quiet:
                continue
            print(f'  {section["heading"]}   ({section["category"]})  '
                  f'{section["body_lines"]} lines')
            if not section["entries"]:
                print("      (no entries parsed)")
            for entry in section["entries"]:
                mark = "BARE" if not (entry["bullets"] + entry["description"]) else \
                       f'{entry["bullets"]}b {entry["description"]}d'
                print(f'      [{mark:>7}]  {entry["title"]}')
        if not quiet:
            if data["orphans"]:
                print(f'  -- {len(data["orphans"])} lines in no section '
                      f'({orphan_share:.0%} of the document):')
                for line in data["orphans"][:6]:
                    print(f'       {line[:70]}')
                if len(data["orphans"]) > 6:
                    print(f'       ... and {len(data["orphans"]) - 6} more')
            print()

    print()
    print("=" * 78)
    print(f"SUMMARY over {len(files)} sample CVs")
    print("=" * 78)
    print(f"{len(no_sections)} CVs where the vocabulary found NO heading at all")
    for label in no_sections:
        print(f"    {label}")
    print(f"{len(orphan_heavy)} CVs where over 40% of the text sits in no section")
    for label, share in sorted(orphan_heavy, key=lambda x: -x[1]):
        print(f"    {share:>4.0%}  {label}")
    print(f"{len(bare_sections)} sections parsed with zero entries")
    for item in bare_sections[:15]:
        print(f"    {item}")
    if len(bare_sections) > 15:
        print(f"    ... and {len(bare_sections) - 15} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
