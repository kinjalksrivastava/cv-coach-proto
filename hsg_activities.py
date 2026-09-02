"""
HSG's own programmes, clubs, certificates and competitions - the thing this bot
can do that a general-purpose LLM cannot.

The list comes from Career Services' "HSG specific activities and opportunities"
document, including their CV-Section column, which is the valuable part: a club
MEMBERSHIP belongs as a bullet under Education, an active ROLE in the same club
belongs under Extracurricular with its own bullets, and a paid shift at the
Talents Conference is Work Experience while volunteering on the day is not.

Scope, deliberately: PROMPTING only. The bot asks whether the student has
already done any of these and, if so, helps them put it in the right section.
It does not recommend joining things to gain experience - that half of Career
Services' request is held back pending their confirmation, which is why
USEFUL_LINKS below is defined but not wired into any prompt.

On links: this file is the single place a URL lives. Nothing here is inferred at
runtime and the bot has no web access, so it cannot notice a dead link or find a
moved page - when a URL changes, one line here changes. That is also why every
entry leads with the programme NAME: a name survives a site restructure, a deep
link does not. See PROJECT_SPEC.md for the link-durability discussion.
"""

# Each entry: (name, what it is, where it goes on a CV, url)
# "where it goes" is Career Services' own mapping, kept in their words where the
# rule is conditional - the condition is the point.

MENTORING = [
    ("HSG Mentoring Programme",
     "two-year one-to-one mentoring, matched with an experienced professional",
     "Education, as a bullet under the degree (name the mentor's industry if relevant)",
     "https://www.unisg.ch/en/studying/starting-your-studies/counselling-services/mentoring-programme/"),
    ("Assessment Guide (SHSG)",
     "peer mentoring through the Assessment Year",
     "Education if they were the mentee; Extracurricular if they were the guide",
     "https://shsg.ch/services"),
]

CLUBS = [
    ("HSG student clubs (~150 accredited, SHSG directory)",
     "the full filterable directory of accredited HSG clubs",
     "membership alone: a bullet under Education if relevant to the role. An active "
     "role: Extracurricular, explained with bullets",
     "https://shsg.ch/clubs"),
    ("Law Clinic", "students give free legal advice to the public, with real client contact",
     "as for any club - membership vs active role", "https://www.unisg.ch/"),
    ("Consulting Club HSG", "case training and a year-long Case Class with Bain & Company",
     "as for any club", "https://consultingclub.ch/"),
    ("Helvetian Investment Club (HIC)",
     "the largest student-run finance society in the DACH region",
     "as for any club", "https://shsg.ch/clubs"),
    ("oikos St. Gallen", "sustainability-focused student association",
     "as for any club", "https://shsg.ch/clubs"),
    ("Entretech", "small teams working on real startup cases for founders",
     "as for any club", "https://entretech.club/"),
    ("LawDays", "St. Gallen's largest student-organised legal careers event",
     "as for any club", "https://shsg.ch/clubs"),
    ("SHSG Student Union", "the umbrella body for all clubs, with its own parliament and board",
     "Extracurricular, if they held an active role", "https://shsg.ch/"),
]

CERTIFICATES = [
    ("Certificate in Data Science Fundamentals (DSF)",
     "Bachelor's-level coding, statistics and data science certificate",
     "Education as a specialisation, or Courses and Certificates",
     "https://www.unisg.ch/en/studying/programmes/bachelor/additional-qualifications/certificate-in-data-science-fundamentals/"),
    ("Certificate in Integrative Sustainability Management (SuM-HSG)",
     "Bachelor's certificate pairing coursework with hands-on impact projects",
     "Education as a specialisation, or Courses and Certificates",
     "https://sustainability.unisg.ch/news/new-bachelor-certificate/"),
    ("Master's Certificate in Managing Climate Solutions (MaCS)",
     "the Master's-level sustainability/climate credential",
     "Education as a specialisation, or Courses and Certificates",
     "https://www.unisg.ch/en/university/engagement/responsibility-and-sustainability/"),
    ("Other Additional Qualification Programmes",
     "Business Education I & II, Digital Communication and Journalism, Financial "
     "Technology, Real Estate - same competitive, transcript-visible format",
     "Education as a specialisation, or Courses and Certificates",
     "https://www.unisg.ch/en/studying/admission/additional-qualification-programmes/"),
    ("Certificate in Wirtschaftspädagogik",
     "the teaching qualification track",
     "Education as a specialisation, or Courses and Certificates", ""),
    ("Bloomberg Market Concepts (BMC)",
     "a 12-hour e-learning introduction to the financial markets, via the HSG library",
     "Technical Skills, or Courses and Certificates", ""),
]

ENTREPRENEURSHIP = [
    ("Startup@HSG / HSG Entrepreneurship",
     "the central entry point to HSG's start-up ecosystem: coaching, space, programmes",
     "Extracurricular, if they were actively involved", "https://startuphsg.unisg.ch/"),
    ("Entrepreneurial Talents Programme (ETP)",
     "supports around ten student ventures a semester with coaching and investor access",
     "Extracurricular", "https://startuphsg.unisg.ch/what-we-offer/entrepreneurial-talents-programme/"),
    ("START Summit",
     "Europe's largest founders' conference, organised entirely by HSG students",
     "an active organising role: Extracurricular. Volunteering on the day only: "
     "Volunteering or Interests",
     "https://www.unisg.ch/en/hsg-at-a-glance/entrepreneurship/"),
    ("Talents Conference (Career Services)",
     "HSG's biggest careers fair, student-organised, with paid part-time roles and "
     "day volunteers",
     "a paid part-time role: Work Experience. Volunteering on the day: Volunteering "
     "or Interests", ""),
    ("HSG Innovation Trophy",
     "student-led innovation case competition set by a corporate partner",
     "Extracurricular", "https://www.hsginnovationtrophy.com/about-1"),
]

FLAGSHIP_EVENTS = [
    ("St. Gallen Symposium (International Students' Committee)",
     "a globally recognised conference organised by a student committee",
     "a full-time staff position: Work Experience. Otherwise Extracurricular",
     "https://shsg.ch/clubs"),
    ("NextGen Impact Forum / SHSG Next Gen Impact Award",
     "student-run conference showcasing HSG sustainability initiatives, with a prize",
     "an active role: Extracurricular. Volunteering on the day: Volunteering or Interests",
     "https://www.unisg.ch/"),
]

SPORT_AND_DIVERSITY = [
    ("HSG University Sports",
     "around 250 training sessions a week across 70+ sports",
     "an active role or teaching a class: Extracurricular, or Work Experience if it "
     "was a paid contract", "https://www.unisg.ch/en/"),
    ("UNIVERSA - The Women's Business Network",
     "the main business network for female students at HSG",
     "Extracurricular, if they held an active role", "https://www.universa-unisg.ch/"),
    # Career Services flagged the rebrand as unconfirmed - both names are carried
    # so the bot never asserts one that may be wrong.
    ("UniGay (rebranding to UniQueer)",
     "LGBTQ+ community at HSG: mentoring, company visits, Get Connected recruiting events",
     "Extracurricular, if they held an active role", "https://www.unigay.ch/english/home/"),
    ("Pride Month @HSG", "student initiative running panels, talks and campus events",
     "Extracurricular, if they held an active role", "https://www.unigay.ch/pride-month-hsg/"),
    ("D&I Week", "annual week presenting D&I research to staff and students",
     "Extracurricular, if they held an active role",
     "https://www.unisg.ch/en/university/engagement/diversity-inclusion/"),
    ("Committee for Equality, Diversity and Inclusion - project funding",
     "grants of CHF 1,000-5,000 for student-proposed D&I projects",
     "Extracurricular, if they ran a funded project", "https://www.unisg.ch/"),
]

ACADEMIC_PROJECTS = [
    ("Bachelor's / Master's thesis",
     "the academic capstone; several institutes welcome theses written with a company",
     "Education", "https://www.unisg.ch/"),
    ("Capstone Project (BWL)",
     "a semester acting as business consultants for a real practice partner",
     "Education", "https://www.unisg.ch/en/studying/programmes/bachelor/major-in-business-administration-bwl/curriculum/"),
    ("Company-linked practical projects (e.g. AWP projects, Student Impact)",
     "teams of 3-6 students working with a partner organisation, ~240 hours each",
     "Education", "https://www.unisg.ch/en/transfer/insights-and-advice-for-partners-from-the-world-of-work/"),
]

COMPETITIONS = [
    ("Global M&A Challenge (GMA)", "the largest student M&A case competition",
     "Extracurricular if involvement was substantial or the team went far; Awards if "
     "they reached the finals", "https://thegmachallenge.org"),
    ("Mavara M&A Case Competition", "Europe-wide remote M&A competition",
     "as for other competitions", "https://mavara-group.com"),
    ("FinanceLab M&A Competition", "Nordic-focused M&A case competition hosted by CBS",
     "as for other competitions", "https://flcomp.dk"),
    ("180 Degrees Consulting - Global Case Competition",
     "global social-impact consulting case competition",
     "as for other competitions", "https://180dc.org"),
    ("Undergrad Case Competition World Cup",
     "virtual undergraduate consulting case competition",
     "as for other competitions", "https://managementconsulted.com"),
]

GROUPS = [
    ("Mentoring and coaching", MENTORING),
    ("Student clubs and associations", CLUBS),
    ("Certificate programmes (additional qualifications)", CERTIFICATES),
    ("Entrepreneurship, innovation and student-run events", ENTREPRENEURSHIP),
    ("Flagship events run by students", FLAGSHIP_EVENTS),
    ("University sports, diversity and inclusion", SPORT_AND_DIVERSITY),
    ("Academic and company-linked projects", ACADEMIC_PROJECTS),
    ("External case competitions", COMPETITIONS),
]

# Defined, deliberately not used yet: pointing students at templates and job
# boards is the "recommending" half of Career Services' request, which is still
# being confirmed. Wiring this in is a one-line change to RULES below.
USEFUL_LINKS = [
    ("HSG CV templates", "good examples to compare against - never to copy verbatim", ""),
    ("HSG cover letter templates", "as above", ""),
    ("My HSG Career", "part-time jobs, internships and company events for HSG students",
     "https://my.hsgcareer.ch"),
]


# A condensed version of the catalogue for the interface, shown to a student
# whose CV has little or no involvement to talk about. Deliberately a GIST:
# category, a handful of recognisable names, and the CV section it belongs in -
# not the full 37 entries, which would read as a wall rather than a starting
# point. Every line is drawn from the same Career Services source as the rest of
# this file, so the panel and the conversation can never disagree.
GIST = [
    ("Mentoring",
     "HSG Mentoring Programme, Assessment Guide (SHSG)",
     "Education — as a bullet under your degree"),
    ("Student clubs",
     "~150 accredited clubs via SHSG — Consulting Club HSG, Helvetian Investment "
     "Club, oikos St. Gallen, Entretech, Law Clinic, LawDays",
     "Membership: a bullet under Education. An active role: Extracurricular"),
    ("Certificates alongside your degree",
     "Data Science Fundamentals (DSF), Integrative Sustainability Management "
     "(SuM-HSG), Managing Climate Solutions (MaCS), Bloomberg Market Concepts",
     "Education as a specialisation, or Courses & Certificates"),
    ("Student-run events",
     "START Summit, St. Gallen Symposium, Talents Conference, NextGen Impact Forum",
     "Organising role: Extracurricular. Paid role: Work Experience. "
     "Volunteering on the day: Volunteering"),
    ("Entrepreneurship",
     "Startup@HSG, Entrepreneurial Talents Programme (ETP), HSG Innovation Trophy",
     "Extracurricular"),
    ("Sports, diversity and inclusion",
     "HSG University Sports (70+ sports), UNIVERSA, UniGay / UniQueer, "
     "Pride Month @HSG, D&I Week",
     "Extracurricular — or Work Experience if you teach a class under contract"),
    ("Academic and company projects",
     "Bachelor's / Master's thesis, Capstone Project, company-linked practical "
     "projects (AWP, Student Impact)",
     "Education"),
    ("Case competitions",
     "GMA Challenge, Mavara, FinanceLab, 180 Degrees Consulting, Undergrad Case "
     "Competition World Cup",
     "Extracurricular — or Awards if you reached the finals"),
]

# Section categories that count as "involvement" when deciding whether a CV has
# enough of it to skip the panel. From guardrails/section_coverage.CATEGORIES.
INVOLVEMENT_CATEGORIES = {
    "Extracurricular & Interests",
    "Volunteering & Community",
    "Projects",
    "Awards & Scholarships",
    "Certifications & Training",
}

MIN_INVOLVEMENT_SECTIONS = 2


def looks_thin(section_categories) -> bool:
    """
    True when this CV has little to show under involvement, and the gist is
    worth surfacing. A CV already carrying two or more of these sections
    doesn't need to be told what exists - it needs help describing what's there.
    """
    return len(INVOLVEMENT_CATEGORIES & set(section_categories)) < MIN_INVOLVEMENT_SECTIONS


def _catalogue() -> str:
    lines = []
    for title, entries in GROUPS:
        lines.append(f"{title}:")
        for name, what, where, _url in entries:
            lines.append(f"  - {name} — {what}. Goes in: {where}.")
    return "\n".join(lines)


CATALOGUE = _catalogue()

RULES = f"""HSG-SPECIFIC PROMPTING. You know St. Gallen's own programmes, clubs, certificates \
and student-run events, and where each belongs on a CV. This is what makes you more \
useful than a general-purpose assistant, and it is the one thing a student cannot get \
elsewhere. Use it as follows.

WHEN: when a section of the CV is thin, missing, or the student says they have nothing \
to put there. Then ask whether they have already done any of the HSG activities that \
belong in THAT section.

HOW:
- Ask about two or three that fit the section being discussed. Never list the catalogue \
at them, and never work through it systematically.
- Ask whether they have done it. Never assume they have, never imply they should have, \
and never state or hint that they participated in something the CV doesn't show.
- If they have done it, say which section it belongs in using the mapping below - the \
membership-versus-active-role distinction matters, and so does paid-versus-volunteer - \
and then apply that section's normal rules: ask what they actually did, what their \
responsibility was, and what changed. A club name on its own says nothing.
- If they haven't done it, accept that immediately and move on. Do not suggest they \
join something, do not describe what they are missing out on, and do not return to it.
- Only ever name activities from the catalogue below. Never invent an HSG club, \
certificate or programme, and never state entry requirements, dates, deadlines or \
selection odds - you do not have that information.
- Don't give out URLs. Name the programme; the student can find it, and a link you \
half-remember may be out of date.

CATALOGUE (Career Services' own list and their own CV-section mapping):
{CATALOGUE}"""

# Shorter form for the opening report, where there's no back-and-forth: the report
# may name an HSG example next to a thin or missing section, phrased as an
# invitation, exactly as Career Services' own sample report does with Bloomberg
# Market Concepts.
REPORT_RULES = f"""HSG-SPECIFIC EXAMPLES. For a section that is thin or missing, you may name \
one or two HSG activities from the catalogue below that would belong there, phrased \
strictly as an invitation - "if you have done X, it belongs here" - never as an \
assumption that they did, never as advice to go and do it, and never with entry \
requirements or deadlines attached. At most two sections in the whole report should \
carry such an example. Only name things from this catalogue.

{CATALOGUE}"""
