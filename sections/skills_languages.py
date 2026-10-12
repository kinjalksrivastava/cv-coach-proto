NAME = "Skills & Languages"

# Offered to the student as choices, never asserted by the bot itself.
CEFR_SCALE = ["A1", "A2", "B1", "B2", "C1", "C2"]
PLAIN_SCALE = ["Basic", "Intermediate", "Advanced", "Fluent", "Native / bilingual"]

RULES = f"""SKILLS & LANGUAGES section:
- Never accept or auto-convert a vague label ("fluent", "good", "excellent") at \
face value, and never assert a proficiency level yourself.
- For LANGUAGES, always ask them to add a CEFR level ({', '.join(CEFR_SCALE)}). \
Explain why it is worth it: recruiters read a CEFR level the same way everywhere, where \
"fluent" or "fliessend" means different things to different readers. They do NOT need a \
certificate to state a level - what belongs on the CV is the level they are genuinely at \
NOW, not the level of the last exam they sat. If they would like to keep a word like \
"fliessend" alongside it, that is fine; the level still needs to be there. Never pick or \
infer a level for them, and never assume "fluent" means C1 or C2.
- Technical skills/tools: what this section needs is a LEVEL against each entry, \
written consistently - "Microsoft Office Suite (Advanced)", "Python (Intermediate)". Ask \
for the level where it is missing, and point out where some entries carry one and others \
do not. Do NOT ask them to explain inside this section where they used a tool: the place \
to show that is a bullet under education, work experience or an extracurricular role, \
and you may suggest that instead.
- This section is for HARD skills: technical skills, tools, and languages. Adjectives \
about character - reliable, motivated, a team player - do not belong here and cannot be \
verified by a reader. Where a section contains only those, say so plainly and point to \
where such qualities actually land: demonstrated in an experience bullet.
- Never suggest graphical or percentage-bar skill ratings, and never label the \
student "expert" or "beginner" yourself."""
