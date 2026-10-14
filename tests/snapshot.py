"""
A complete, deterministic snapshot of what the pipeline makes of every sample CV.

The point is refactoring safely. A change to the parser is only acceptable if it
leaves every measurable the same or visibly better, and "visibly" needs a
baseline to compare against - 26 CVs, every section, every entry, every title,
every date, every bullet, every finding, in one file.

Section detection is a model call, so its result is STORED in the snapshot and
replayed on later runs. Without that, re-running compares a parser change
against model variance and tells you nothing. The model-backed bullet and date
readers are skipped for the same reason; they are additive and untouched by
parser work.

    python tests/snapshot.py --write baseline.json     record
    python tests/snapshot.py --check baseline.json     compare, and exit 1 on a diff
"""

import glob
import json
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv_facts                                                    # noqa: E402
import severity                                                    # noqa: E402
from extraction import extract_text                                # noqa: E402
from guardrails import dates, language, section_coverage           # noqa: E402
from pii import select_cv_content, strip_pii                       # noqa: E402

SAMPLES = os.path.expanduser("~/Downloads/CV Samples")
EXTRA = [os.path.expanduser("~/Downloads/st_gallen_doc/Resume_PhD.pdf")]


def _files() -> list[str]:
    found = [p for p in sorted(glob.glob(SAMPLES + "/**/*.*", recursive=True))
             if p.lower().endswith((".pdf", ".docx"))]
    return found + [p for p in EXTRA if os.path.exists(p)]


def _client():
    with open(".streamlit/secrets.toml", "rb") as handle:
        key = tomllib.load(handle)["OPENAI_API_KEY"]
    from openai import OpenAI
    return OpenAI(api_key=key)


def measure(path: str, cached_sections=None, client=None) -> dict:
    name = os.path.basename(path)
    with open(path, "rb") as handle:
        result = extract_text(handle.read(), name)
    lang = language.detect_message_language(result.text) or "en"
    selected = select_cv_content(result.text)
    clean = strip_pii(selected["text"], lang)
    text = clean["text"]

    sections = cached_sections
    if sections is None:
        sections = section_coverage.detect_sections(text, client, "gpt-4.1")

    blocks = []
    for block in cv_facts._split_sections(text, sections):
        entries = []
        for entry in cv_facts._entries(block["lines"]):
            ranges = dates.extract_ranges(f"{entry['title_line']} {entry['line']}")
            entries.append({
                "line": entry["line"],
                "title": entry["title_line"],
                "dates": [r["raw"] for r in ranges],
                "role": cv_facts._has_role_title(entry),
                "bullets": entry["bullets"],
            })
        blocks.append({"heading": block["heading"], "category": block["category"],
                       "entries": entries})

    facts = cv_facts.analyse(text, result.meta, sections, None, lang)
    ranked = severity.assess(facts)
    return {
        "language": lang,
        "space_share": round(text.count(" ") / max(len(text), 1), 4),
        "pii": {"dropped": selected["dropped_lines"],
                "removed": clean["redactions"], "residual": clean["residual"]},
        "sections": [{"heading": s["heading"], "category": s["category"],
                      "index": s["index"]} for s in sections],
        "blocks": blocks,
        "total_bullets": facts["total_bullets"],
        "entry_count": sum(s["entry_count"] for s in facts["sections"]),
        "status": ranked["section_status"],
        "issues": [{"tier": i["tier"], "key": i["key"]} for i in ranked["all_issues"]],
        "key_areas": [i["key"] for i in ranked["key_areas"]],
        "date_findings": [f["text"] for f in facts["date_findings"]],
        "_sections_raw": sections,
    }


def _walk(value, trail=""):
    """Every leaf in the snapshot, as path -> value, so a diff can name it."""
    if isinstance(value, dict):
        for key, inner in value.items():
            if key == "_sections_raw":
                continue
            yield from _walk(inner, f"{trail}.{key}")
    elif isinstance(value, list):
        for index, inner in enumerate(value):
            yield from _walk(inner, f"{trail}[{index}]")
    else:
        yield trail, value


def main() -> int:
    mode, target = sys.argv[1], sys.argv[2]
    if mode == "--write":
        client = _client()
        snapshot = {os.path.basename(p): measure(p, None, client) for p in _files()}
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, indent=1, ensure_ascii=False)
        entries = sum(v["entry_count"] for v in snapshot.values())
        bullets = sum(v["total_bullets"] for v in snapshot.values())
        print(f"recorded {len(snapshot)} CVs, {entries} entries, {bullets} bullets "
              f"-> {target}")
        return 0

    with open(target, encoding="utf-8") as handle:
        before = json.load(handle)
    differences = 0
    for name, old in before.items():
        path = next((p for p in _files() if os.path.basename(p) == name), None)
        if path is None:
            print(f"MISSING  {name}")
            differences += 1
            continue
        new = measure(path, old["_sections_raw"])
        old_leaves, new_leaves = dict(_walk(old)), dict(_walk(new))
        for key in sorted(set(old_leaves) | set(new_leaves)):
            was, now = old_leaves.get(key, "<absent>"), new_leaves.get(key, "<absent>")
            if was != now:
                differences += 1
                print(f"\n{name}{key}")
                print(f"   was: {was!r}"[:200])
                print(f"   now: {now!r}"[:200])
    print(f"\n{differences} difference(s) across {len(before)} CVs")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
