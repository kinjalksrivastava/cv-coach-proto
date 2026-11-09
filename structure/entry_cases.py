"""
Where a bare entry sits must not change whether it is found.

The report names the entries that carry no description, so the thing that
must never happen is for position to decide. A first job directly beneath the
heading, a bare one between two full ones, a bare one at the end - each has
to come out the same way, or the advice the student reads depends on the
order they happened to list their jobs in.

    ./venv/bin/python structure/entry_cases.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structure import text_layout, tree                           # noqa: E402

FULL = """  - Rebuilt the monthly reporting pack, cutting two days off the close
  - Ran reconciliations across four entities"""

CASES = [
    ("first entry has bullets, second bare", f"""Work Experience
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
{FULL}
Kellner, Gourmetkoch, Bonn                            09/2020 - 01/2022
""", 2, ["Kellner"]),

    ("FIRST entry bare, second has bullets", """Work Experience
Kellner, Gourmetkoch, Bonn                            09/2020 - 01/2022
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
  - Rebuilt the monthly reporting pack, cutting two days off the close
  - Ran reconciliations across four entities
""", 2, ["Kellner"]),

    ("bare entry in the MIDDLE of three", f"""Work Experience
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
{FULL}
Kellner, Gourmetkoch, Bonn                            09/2020 - 01/2022
Intern, Muster GmbH, Basel                            06/2019 - 08/2019
{FULL}
""", 3, ["Kellner"]),

    ("only one entry, and it is bare", """Work Experience
Kellner, Gourmetkoch, Bonn                            09/2020 - 01/2022
""", 1, ["Kellner"]),

    ("every entry bare", """Work Experience
Kellner, Gourmetkoch, Bonn                            09/2020 - 01/2022
Barista, Cafe Muster, Bern                            01/2019 - 08/2019
""", 2, ["Kellner", "Barista"]),

    ("no entry bare", f"""Work Experience
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
{FULL}
Intern, Muster GmbH, Basel                            06/2019 - 08/2019
{FULL}
""", 2, []),

    ("first entry directly under the heading, no blank line", f"""Work Experience
Analyst, Beispiel AG, Zurich                          09/2022 - 08/2024
{FULL}
""", 1, []),
]


def main() -> int:
    failed = 0
    for name, text, entries, bare_titles in CASES:
        doc = tree.build(text_layout.read_text(text))
        found = [e for s in doc.sections for e in s.entries]
        bare = [e.title for e in found if e.is_bare]
        problems = []
        if len(found) != entries:
            problems.append(f"{len(found)} entries, expected {entries}")
        for want in bare_titles:
            if not any(want in title for title in bare):
                problems.append(f"{want!r} should be reported as bare")
        for title in bare:
            if not any(want in title for want in bare_titles):
                problems.append(f"{title[:40]!r} wrongly reported as bare")
        if problems:
            failed += 1
            print(f"FAIL  {name}")
            for problem in problems:
                print(f"        {problem}")
            for e in found:
                print(f"        [{'BARE' if e.is_bare else str(len(e.bullets)) + 'b'}] "
                      f"{e.title[:54]}")
        else:
            print(f"ok    {name}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} entry-position cases correct")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
