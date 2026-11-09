"""
What is actually on each sample CV, written down by reading it.

Every measurement in this project has so far been scored against another
measurement: the sweep recomputed severity's own answer and agreed with it,
the snapshots compared today's output with yesterday's, and the bullet count
was whatever the parser said it was. None of that can tell a fix from a
regression, which is how a round-4 correction went into a constant only the
test file read and the suite stayed green.

This file is the exception. It is hand-written from the rendered pages, one
CV at a time, and it owes nothing to any parser. When the numbers here and
the numbers out of the tree disagree, the tree is wrong.

Counting rules, fixed once so the labels stay comparable:

  SECTION   a heading printed on the page, plus any block that clearly acts
            as one where the CV prints no headings at all.
  ENTRY     one role, degree or activity that carries its own dates. An
            employer with two roles under it is TWO entries, because each
            has its own dates and its own bullets and the report speaks
            about them separately.
  BULLET    one point. A point wrapping onto a second line is one bullet,
            not two - that is the error that inflated the count to 264.
  BARE      an entry with no bullets and no description line of its own. A
            strap line under the employer counts as description.
  ITEMS     a section built of lines rather than dated entries: languages,
            skills, interests, certificates. Its lines are items, and a
            bullet count of 0 for such a section is correct, not a miss.
"""

# name -> {"sections": [(heading, kind, [bullets per entry in order])], "note": str}
# kind is "entries" or "items"; for an items section the list holds the item count.
TRUTH: dict[str, dict] = {

    "Good Student CVs/good cv 1.pdf": {
        "sections": [
            ("AUSBILDUNG", "entries", [2, 2]),
            ("ARBEITSERFAHRUNG", "entries", [2, 3, 3, 2, 2, 2]),
            ("AUSSERCURRICULARE AKTIVITÄTEN", "entries", [2, 1]),
            ("ZUSÄTZLICHE INFORMATIONEN", "items", 4),
        ],
        "bare": [],
        "note": "START Global carries two roles, each with its own dates and "
                "bullets, so it is two entries. Several employers print an "
                "italic strap line above the role; that is description.",
    },

    "Good Student CVs/good cv 2.pdf": {
        "sections": [
            ("EDUCATION", "entries", [0, 0, 0]),
            ("WORK EXPERIENCE", "entries", [3, 3, 2]),
            ("EXTRACURRICULAR ACTIVITIES", "entries", [3, 4]),
            ("SKILLS, ACTIVITIES & INTERESTS", "items", 4),
        ],
        "bare": ["University of St. Gallen", "Universidad Carlos III",
                 "Gymnasium Campus Muristalden"],
        "note": "Education entries carry a degree line but no bullets - they "
                "are genuinely bare. One Impulse Network bullet wraps onto a "
                "second line and is one bullet.",
    },

    "Good Student CVs/good cv 3.pdf": {
        "sections": [
            ("EDUCATION", "entries", [0, 0, 0]),
            ("PROFESSIONAL EXPERIENCE", "entries", [3, 3, 3, 3, 3]),
            ("COMMUNITY EXPERIENCE", "entries", [0, 0, 0]),
            ("ADDITIONAL INFORMATION", "items", 3),
        ],
        "bare": [],
        "note": "Education and Community entries carry one unbulleted line of "
                "description each, so none is bare. Two experience entries open "
                "with an unmarked line before their dashes; those are points too.",
    },

    "Good Student CVs/good cv 4.pdf": {
        "sections": [
            ("EDUCATION", "entries", [0, 0, 0]),
            ("PROFESSIONAL EXPERIENCE", "entries", [5, 2, 2, 1]),
            ("EXTRACURRICULAR ACTIVITY", "entries", [2]),
            ("SKILLS & INTERESTS", "items", 3),
        ],
        "bare": ["Kantonsschule Heerbrugg"],
        "note": "Dates sit in a left-hand column. The two university entries "
                "carry a Relevant Courses line; the Kantonsschule has nothing "
                "under it and is genuinely bare.",
    },

    "Good Student CVs/good cv 5.pdf": {
        "sections": [
            ("EDUCATION", "entries", [3, 2, 2]),
            ("WORK EXPERIENCES", "entries", [4, 3]),
            ("LEADERSHIP", "entries", [5]),
            ("VOLUNTEERING, SOCIETIES & INTERESTS", "items", 7),
            ("FOREIGN LANGUAGES, CERTIFICATES & PROGRAMMING", "items", 3),
        ],
        "bare": [],
        "note": "Bullets are a Wingdings arrow recorded in the file as a plain "
                "ASCII '>' in Times New Roman. No glyph list can contain that; "
                "the marker has to be learned from the document.",
    },

    "Good Student CVs/good cv 6.pdf": {
        "sections": [
            ("EDUCATION", "entries", [0, 3]),
            ("WORK EXPERIENCE", "entries", [2, 4, 1]),
            ("EXTRACURRICULARS", "entries", [2, 2, 1, 2]),
            ("ADDITIONAL INFORMATION", "items", 4),
        ],
        "bare": ["University of St. Gallen"],
        "note": "Bullets use a very small middot and sit in a column of their "
                "own, so per-column indent normalisation currently reports them "
                "as OUTDENTED from the entry titles and loses almost all of them.",
    },

    "Good Student CVs/good cv 7.pdf": {
        "sections": [
            ("Academic Experience", "entries", [0, 1, 0, 0]),
            ("Professional Experience", "entries", [3, 3, 3, 4, 4, 2]),
            ("Extracurriculars", "entries", [1, 0, 1]),
            ("Skills & Interests", "items", 3),
        ],
        "bare": ["EM Lyon", "Bachelor of Arts in Business Administration",
                 "Seycove Secondary School", "Symposium St. Gallen"],
        "note": "Four genuinely bare entries, three of them degrees. Headings "
                "are title case at body size, not capitals.",
    },

    # Serena's round 6 CV. ORGANISATIONEN is the section she reported as
    # wrongly marked Strong: two of its three entries have nothing under them.
    "Bad Student CVs/bad cv 1.pdf": {
        "sections": [
            ("AUSBILDUNG", "entries", [0, 0, 0]),
            ("BERUFSERFAHRUNG", "entries", [6, 7]),
            ("ORGANISATIONEN", "entries", [0, 0, 0]),
            ("SPRACHEN", "items", 5),
            ("SKILLS", "items", 3),
            ("CERTIFICATIONS", "items", 3),
            ("INTERESTS", "items", 5),
        ],
        "bare": ["Assessment Jahr", "Passerelle", "Kauffrau EFZ, Berufsmatura",
                 "UNIVERSA", "START Global"],
        "note": "Headings carry decorative icons from an icon font, recorded "
                "as ordinary letters. Ministrantenscharr has a two-line "
                "description so it is not bare; UNIVERSA and START Global are.",
    },

    "Bad Student CVs/bad cv 2.pdf": {
        "sections": [
            ("EDUCATION", "entries", [0, 0]),
            ("WORK EXPERIENCE", "entries", [0, 0]),
            ("CORE COMPETENCES", "items", 7),
            ("LANGUAGES", "items", 2),
            ("HOBBIES AND INTERESTS", "items", 3),
        ],
        "bare": ["Bismarck Gymnasium", "St. Gallen Symposium, Responsible",
                 "St. Gallen Symposium, Project Manager"],
        "note": "Core Competences divides into Technical skills and Personal "
                "skills, each a bulleted list - items, not entries, so those "
                "seven bullets are not entry bullets. The Bachelor entry "
                "carries a grade line, so it is not bare.",
    },

    "Bad Student CVs/bad cv 3.pdf": {
        "sections": [
            ("AUSBILDUNG", "entries", [0, 0]),
            ("BERUFSERFAHRUNG", "entries", [0]),
            ("SPRACHEN", "items", 4),
            ("ENGAGEMENT", "entries", [0, 0]),
        ],
        "bare": ["Universität St. Gallen (HSG)", "Kantonsschule Frauenfeld",
                 "Flugbegleiterin", "Jugendrätin", "Co-Präsidentin"],
        "note": "Genuinely sparse: every entry on this CV is a single line "
                "with nothing under it. Five bare entries is the correct "
                "answer here, not a parser failure.",
    },

    "Bad Student CVs/bad cv 4.pdf": {
        "sections": [
            ("Ausbildung", "entries", [0, 0]),
            ("Berufserfahrung", "entries", [0, 1, 1, 1]),
            ("Zertifikate", "items", 3),
            ("Kenntnisse", "items", 4),
            ("Engagement", "items", 3),
        ],
        "bare": ["Universität St. Gallen HSG", "Liechtensteinisches Gymnasium",
                 "Kurzpraktikum, Werkhof Ruggell"],
        "note": "Nothing on this page is bold, larger or capitalised - one "
                "font at one size throughout, with even spacing. The headings "
                "can only be found by what follows them.",
    },

    "Bad Student CVs/bad cv 5.pdf": {
        "sections": [
            (None, "entries", [0, 0, 0, 0, 0]),
            (None, "entries", [0, 0]),
            (None, "items", 4),
        ],
        "bare": ["Language Exchange", "Helper with counting", "Member of the Marketing Club"],
        "note": "No headings at all - they are part of the background image. "
                "Three blocks separated by 37pt and 44pt of white space "
                "against 8-10pt inside a block. Dates sit in a left column.",
    },

    "Bad Student CVs/bad cv 6.pdf": {
        "sections": [
            ("SPRACHEN", "items", 2),
            ("IT-KENNTNISSE", "items", 3),
            ("ENGAGEMENT", "items", 3),
            ("INTERESSEN", "items", 2),
            ("BERUFSERFAHRUNG", "entries", [2, 2, 1]),
        ],
        "bare": [],
        "note": "A true sidebar: a dark narrow column of languages, skills "
                "and interests beside a main column of experience. The two "
                "are separate flows and must not be read row by row across "
                "the page.",
    },

    "Bad Student CVs/bad cv 7.pdf": {
        "sections": [
            ("Beruflicher Werdegang", "entries", [2, 4, 3, 3]),
            ("Ausbildung", "entries", [0, 0, 0, 0]),
            ("Kompetenzen", "items", 3),
            ("Sprachen", "items", 4),
            ("Hobbies", "items", 3),
        ],
        "bare": [],
        "note": "Dates in a left column. Education entries carry two to four "
                "unbulleted description lines each, so none is bare. Carries "
                "a real hyperlink in one bullet.",
    },

    # Miriam's round 6 CV. The gastronomy entry is the only bare one in the
    # experience section, which is the whole of her complaint.
    "Bad Student CVs/bad cv 8.pdf": {
        "sections": [
            ("AUSBILDUNG", "entries", [0, 3, 1]),
            ("ARBEITS- & FÜHRUNGSERFAHRUNGEN", "entries", [4, 2, 7, 0]),
            ("Fremdsprachenkenntnisse", "items", 4),
            ("Engagements", "entries", [6, 1, 0]),
            ("Interessen", "items", 1),
        ],
        "bare": ["Kellner", "Ehrenamtlicher Wahlhelfen"],
        "note": "Three bullet levels in three glyphs - a filled circle, a "
                "Courier o and a small square. The last section divides into "
                "three sub-headings, two of them lists and one of them "
                "entries. Hochschule St. Gallen carries two description "
                "lines, so it is not bare.",
    },

    "Bad Student CVs/bad cv 9.pdf": {
        "sections": [
            ("Schul- und Berufsausbildung", "entries", [0, 0, 0, 0, 0, 0, 0, 0]),
            ("Praktische Erfahrungen", "entries", [0, 0]),
            ("Ehrenamtliche Tätigkeiten", "entries", [0, 0, 0, 0]),
            ("Zusätzliche Teilnahmen", "entries", [0]),
        ],
        "bare": ["Auszeit aus privaten Gründen"],
        "note": "Not a single bullet on the CV. Every entry carries two to "
                "four unbulleted description lines instead, so only the "
                "Auszeit entry is genuinely bare. Dates in a left column.",
    },

    "Bad Student CVs/bad cv 10.pdf": {
        "sections": [
            ("EDUCATION", "entries", [1, 2]),
            ("WORK EXPERIENCE", "entries", [1, 1, 1, 1, 1]),
            ("SKILLS & LANGUAGES", "items", 1),
            ("DIPLOMAS & CERTIFICATIONS", "items", 3),
            ("EXTRACURRICULAR & OTHER", "items", 3),
        ],
        "bare": [],
        "note": "Headings are letter-spaced small capitals. The text layer "
                "is damaged: EDUCATION arrives as EDUCAT10N and SKILLS as "
                "SKILES, which is why heading vocabulary cannot be relied on.",
    },

    "Bad Experienced CVs/exp cv bad 1.pdf": {
        "sections": [
            ("BESONDERE SKILLS", "items", 4),
            ("PERSÖNLICHE DATEN", "items", 5),
            ("SPRACHEN", "items", 2),
            ("FREIZEIT", "items", 2),
            ("REFERENZEN", "items", 1),
            ("BERUFLICHE ERFAHRUNG", "entries", [3, 0, 0, 0, 0, 0, 3]),
            ("AUSBILDUNG", "entries", [0, 0, 0, 0, 0]),
        ],
        "bare": ["LEAD BUYER INDIRECTS", "JUNIOR CONSULTANT ERP-SYSTEME",
                 "JUNIOR LEAD BUYER", "JUNIOR BUYER", "PRAKTIKANT EINKAUF",
                 "Berufsbildner", "CAS in Supply Chain", "Bachelor Business",
                 "Sport / BWL Studium", "Sportgymnasium"],
        "note": "A true sidebar, headings centred in the narrow column. Ten "
                "genuinely bare entries - this CV lists job titles with dates "
                "and nothing else. The Handballspieler block sits under the "
                "experience heading with three bullets of its own. The "
                "sidebar carries a full postal address, so PII matters here.",
    },

    "Bad Experienced CVs/cv exp bad 2.pdf": {
        "sections": [
            ("EMPLOYMENT HISTORY", "entries", [8, 3, 1]),
            ("EDUCATION", "items", 4),
            ("ADDITIONAL EXPERIENCE / SKILLS", "items", 4),
            ("ADDITIONAL ACTIVITIES", "items", 4),
        ],
        "bare": [],
        "note": "Opens with an unheaded profile paragraph. AXA XL nests six "
                "Courier-o sub-bullets under one filled-circle bullet; all "
                "eight are points. Education is written as prose lines with "
                "inline dates rather than as dated entries.",
    },
}
