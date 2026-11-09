"""
The tree written back out as text, for the model to read.

The model is not given the tree. It is given prose, because that is what it
reads well - but prose in the order a person reads the page, which a flat
extraction does not produce. On a CV with a sidebar the flat text interleaves
the two columns line by line, so a heading from the margin lands in the
middle of a job title:

    BESONDERE
    SKILLS CATEGORY LEAD INDIRECT SERVICES & IT CENTRAL EUROPE WANDER AG

That is bad for the report, and it is worse than that for privacy. On the
same CV the student's street address and the line "JUNIOR LEAD BUYER WANDER
AG" were welded into one line, the address pattern matched the whole of it,
and the job title was redacted along with the address - losing exactly the
information the tool exists to comment on.

Reading the columns in order fixes both at once.
"""

from __future__ import annotations

from .tree import Document, Section


def render(document: Document) -> str:
    out: list[str] = []
    if document.preamble:
        out += document.preamble + [""]
    for section in document.sections:
        _section(section, out, level=0)
    return "\n".join(out).strip() + "\n"


def _section(section: Section, out: list[str], level: int) -> None:
    heading = section.heading or "(section with no readable heading)"
    out.append(("  " * level) + heading)
    for entry in section.entries:
        out.append(("  " * level) + "  " + entry.title)
        for kind, text in (entry.content or
                           [("line", l) for l in entry.description]
                           + [("bullet", b) for b in entry.bullets]):
            mark = "- " if kind == "bullet" else ""
            out.append(("  " * level) + "    " + mark + text)
    for item in section.items:
        out.append(("  " * level) + "  " + item)
    for child in section.subsections:
        _section(child, out, level + 1)
    out.append("")
