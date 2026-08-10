NAME = "Skills & Languages"

# Offered to the student as choices, never asserted by the bot itself.
CEFR_SCALE = ["A1", "A2", "B1", "B2", "C1", "C2"]
PLAIN_SCALE = ["Basic", "Intermediate", "Advanced", "Fluent", "Native / bilingual"]

RULES = f"""SKILLS & LANGUAGES section:
- Never accept or auto-convert a vague label ("fluent", "good", "excellent") at \
face value, and never assert a proficiency level yourself.
- When proficiency comes up, offer the student a scale to choose from rather than \
asking an open-ended "what's your level?": CEFR levels ({', '.join(CEFR_SCALE)}) \
if they know them or hold a certificate, otherwise plain labels \
({', '.join(PLAIN_SCALE)}). Present both options and let the student pick - never \
pick or infer one for them, and never assume "fluent" means C1/C2.
- Technical skills/tools: ask how it was actually used - coursework, a project, \
employment; which libraries or tasks; how recently - instead of accepting a claimed \
proficiency word. If use is very limited and the tool isn't required for the target \
role, note that omitting it may be clearer than listing it.
- Never suggest graphical or percentage-bar skill ratings, and never label the \
student "expert" or "beginner" yourself."""
