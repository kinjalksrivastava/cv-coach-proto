"""
What the tree supports saying, rendered in code.

This is the half of the report that must never be left to the model. The
model writes the prose; the claims come from here, each one naming the entry
it is about. Career Services' two standing complaints are both failures of
this layer, not of the writing:

  "It shows Organisationen as strong, even though the person has not added
   any details or bullets to their experiences"                  - Serena, R6

  "This CV gets the information, that they should have bullet points under
   each job description but the person has bullet points under each job
   apart from the one in gastronomy."                            - Miriam, R6

The first is a section nobody measured. The second is a true measurement
turned into false advice on its way to the page. Naming the entry fixes both,
and neither needs a list of exempt job types.
"""

from __future__ import annotations

from .tree import Document, Section


def assess_section(section: Section) -> dict:
    """
    Facts about one section, and nothing that is not a fact.

    An entry section is judged on whether each entry says what was done. An
    item section - languages, skills, interests - is not: demanding bullets
    there is the invented problem Career Services has reported twice.
    """
    if section.entries:
        bare = [e for e in section.entries if e.is_bare]
        thin = [e for e in section.entries
                if not e.is_bare and len(e.bullets) + len(e.description) < 2]
        return {
            "kind": "entries",
            "total": len(section.entries),
            "described": len(section.entries) - len(bare),
            "bare": [e.title for e in bare],
            "thin": [e.title for e in thin],
            "status": "needs_attention" if bare else "strong",
        }
    return {
        "kind": "items",
        "total": len(section.items),
        "bare": [],
        "thin": [],
        "status": "strong",
    }


def render(document: Document) -> str:
    out: list[str] = []
    for section in document.sections:
        _render_section(section, out, depth=0)
    return "\n".join(out)


def _render_section(section: Section, out: list[str], depth: int) -> None:
    pad = "    " * depth
    if section.subsections:
        out.append(f"{pad}{section.heading or '(a block with no heading)'}")
        for child in section.subsections:
            _render_section(child, out, depth + 1)
        out.append("")
        return
    _render_leaf(section, out, pad)


def _render_leaf(section: Section, out: list[str], pad: str) -> None:
    if True:
        facts = assess_section(section)
        name = section.heading or "(a block with no heading)"
        mark = "Needs attention" if facts["status"] == "needs_attention" else "Strong"
        out.append(f"{pad}{name}   -  {mark}")
        if facts["kind"] == "items":
            out.append(f"{pad}    A list of {facts['total']} items, not entries. "
                       f"Nothing here is expected to carry bullets.")
            out.append("")
            return
        out.append(f"{pad}    {facts['described']} of {facts['total']} entries say "
                   f"what you actually did.")
        if facts["bare"]:
            out.append(f"{pad}    These carry no description at all:")
            for title in facts["bare"]:
                out.append(f"{pad}      - {title[:72]}")
            out.append(f"{pad}    Whether each of those needs one is your call: a "
                       f"short student job often reads")
            out.append(f"{pad}    fine without. Add detail where there is something "
                       f"to say.")
        if facts["thin"]:
            out.append(f"{pad}    These say very little:")
            for title in facts["thin"]:
                out.append(f"{pad}      - {title[:72]}")
        out.append("")
