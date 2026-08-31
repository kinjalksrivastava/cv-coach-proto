# CV Coach — project spec (handoff doc)

Source of truth for iterative development. Pulled from `cv_coach_requirements.docx`,
`tech_requirements.docx` (10 user stories + edge cases), `HSG_Top_Job_Categories.docx`,
and clarifications from the person building this on 2026-08-10. Give this whole file
to Claude Code as context before asking it to build on top of the existing prototype
in this repo.

## 1. What this is

A conversational CV-feedback tool for HSG Career Services. A student uploads a CV
(and optionally a job description), and the bot asks questions that guide the student
to strengthen their own CV — it never scores it and never writes text for them.

## 2. Intake rules

- **CV: required.** Word (.docx) or PDF, either is fine — no other format
  requirement. No visual/layout judgment is ever given, since only extracted text is
  available downstream.
- **Job description: optional.** Paste or upload, either is fine. A student can use
  the tool to generally strengthen a CV with no job description at all — the bot must
  not block or nag for one. If none is provided, or none arrives after one follow-up
  question, give structure-and-completeness feedback rather than role-specific
  feedback, and say that's what it's doing.
- **Images (profile photos, signatures, etc.) are never analyzed.** Only extracted
  text ever reaches the pipeline, so this is mostly automatic — but don't add any
  future code path (e.g. OCR, vision-model calls) that would read an embedded photo.
- **Language: ask once at session start** ("English or Deutsch?"), and use that as
  the default. But if the student then writes in the other language, follow what they
  actually write from that point on — the upfront answer is a starting default, not a
  lock. Detect per-message, not just once.
- **Latency: under 6 seconds per turn.** This is a hard product rule, not a nice-to-have.
  Practical levers: stream the model response (perceived latency drops even if total
  generation time doesn't), keep the system+context prompt lean, avoid chaining two
  full model calls per turn where one will do (today's score-check retry is the one
  justified exception), and set an explicit request timeout with a graceful fallback
  message rather than a silent hang.

### 2b. Two deliberate exceptions, agreed with Career Services (2026-09-01)

The feedback report Career Services asked for needs two things the hard rules below
originally forbade. Both are scoped as narrowly as possible; everything else still holds.

| Exception | Scope |
|---|---|
| **Evaluative marks in the report** | Strong / Needs attention / Missing, and a high/medium mark on each improvement area. These are the only evaluative device anywhere in the product. No number, percentage, grade, letter or ranking appears in the report or in the conversation, and the conversation itself still never labels anything. |
| **Generic example bullets in the report** | A fixed table of weak-vs-strong bullet examples, reproduced verbatim from Career Services' own sample document, shown only when the CV has responsibility-shaped bullets. It is never generated, never adapted to the student's content, and never applied to a line they wrote. "Never rewrite" is unchanged for everything touching the student's own wording. |
| **Format observations** | Length, text density and ATS compatibility, and only from facts measured from the file (page count, fonts, tables, images, heading wording, bullet characters). The "content not layout" rule still forbids any judgement of visual design, and the report says outright that whitespace isn't observable. |

## 3. Hard global rules (apply to every turn, every section)

| Rule | Detail |
|---|---|
| Never score | No number, percentage, letter grade, or good/bad label — for the CV, a section, or a bullet. |
| Never invent | No fact, number, tool, or outcome not present in the CV, the JD, or what the student said in-chat. |
| Never assume absence = omission | Ask whether something exists (grade, exchange, student job, thesis detail) before treating it as missing. |
| **Never rewrite — suggestions only** | No bullet, section, or letter is ever written or reworded for the student, even on repeated request, even reframed as "just an example." Translating the student's own existing wording is fine. Everything the bot offers is a question or a suggestion of *what to consider*, never drafted text. |
| Area & content only | Never comment on layout, font, spacing — only extracted text is available. |
| Target role before feedback | Don't give role-specific feedback until a target role/industry/JD is known (see intake rules for the JD-optional fallback). |
| Confidentiality → handover | NDA, compensation, salary, offer-term mentions stop coaching on that topic; ask to confirm before flagging for a human advisor. |
| Bilingual, adaptive | See intake rules above. |
| Latency budget | Under 6s per turn. See intake rules above. |

## 4. Per-section rules

### Education
| Rule | Source |
|---|---|
| Grades: ask whether available and worth including before recommending; never invent a grade | Story 2 |
| Prioritize latest degree/current GPA; treat earlier grades (Matura etc.) as context-dependent, not universally required | Story 2 |
| Thesis: ask what was actually done (dataset, method, tool, output) — never infer technical skills from the title alone | Story 5 |
| Exchange semester: ask directly whether one exists before commenting on its absence; accept "no" without treating it as a gap; don't raise it again once answered | Story 9 |
| Date formats/order: flag genuine gaps and overlaps for the bot to ask about — never assume a gap is a weakness | today's addition, built (`guardrails/dates.py`) |

### Experience (professional experience / student jobs)
| Rule | Source |
|---|---|
| Thin bullets: ask What / How / Why / Result (what was done, how, who benefited, what changed) | Story 3 |
| Quantify only with evidence the student actually provides; never invent numbers or outcomes | Story 3 |
| Year-of-study calibration: ask year of study before commenting on a missing student job; expected for early-stage, possible real gap for final-year | Story 10 |
| Return offer: treat as evidence of performance, suggest a brief outcome line; if compensation/terms come up, hand over immediately | Story 8 |
| Overlapping or unclear employment dates — ask whether concurrent (e.g. part-time during studies) before treating as an error | edge case, built (`guardrails/dates.py`) |

### Extracurricular activities & interests
| Rule | Source |
|---|---|
| Single-word interests: ask for detail (what kind, how often) before judging | Story 7 |
| Never invent detail, assume a specific meaning ("Sports" → a specific sport), or suggest deleting an interest without asking first | Story 7 |
| Soft-skill claims: ask for concrete situations (team size, what was coordinated, presented, negotiated) — never infer leadership or teamwork from a title alone | Story 4 |

### Skills & languages
| Rule | Source |
|---|---|
| Don't accept or auto-convert vague labels ("fluent", "good") | Story 6 |
| When asking for a level, suggest a scale for the student to pick from — CEFR (A1–C2) where applicable, plus plain-language options (e.g. "intermediate", "native") where CEFR doesn't fit — the bot offers the scale, the student picks; never assert a level itself | today's addition, built (`sections/skills_languages.py`) |
| Tools/software: ask how it was actually used (coursework, project, employment; which libraries/tasks; how recently) instead of accepting a proficiency label at face value | Story 6 |
| Never suggest graphical/percentage skill bars or label the student "expert"/"beginner" | Story 6 |

### Any other section the CV actually has
| Rule | Source |
|---|---|
| Section headings are parsed from the document itself, verbatim and in order, not matched against a fixed list — so Publications & Research, Projects, Certifications & Training, Awards & Scholarships, Volunteering, Profile/Summary, References, Military Service and anything else get coached too | 2026-08-31 change, built (`guardrails/section_coverage.py`) |
| Refer to each section by the heading the student's own CV uses, not by our category name | 2026-08-31 change, built (`prompts.PROACTIVE_COVERAGE`) |
| Publications: ask for the student's own contribution; never infer it from author order or title, never comment on journal prestige or citation counts | 2026-08-31 change, built (`sections/other_sections.py`) |
| Projects / certifications / awards / volunteering: ask what was actually done and what the selection basis was; never rank them against each other | 2026-08-31 change, built (`sections/other_sections.py`) |

### Job description alignment (cross-cutting, not a CV section but a mode)
| Rule | Source |
|---|---|
| JD is optional — see intake rules | today's clarification |
| When a JD exists, compare CV content against it section by section, referencing specific JD requirements | general, Stories 1–10 |
| Skill/requirement mismatch: state it factually, ask about unlisted relevant experience — never tell the student to hide or remove the mismatched skill | edge case |
| Structure-only fallback when no JD/role after one follow-up | edge case, built (`sections/jd_alignment.py` + `app.py` follow-up counter) |

## 5. Current codebase (this repo) — updated after the 2026-08-31 session

The modular structure this section used to propose is now built. Layout:

```
cv_coach/
  app.py                          # orchestration only — no rule text, no styling
  ui.py                            # stylesheet, HSG masthead, cards/chips
  report.py                        # the opening feedback report
  format_check.py                  # length / density / ATS rows, measured from the file
  assets/                          # University of St.Gallen logo (EN/DE) + favicon
  prompts.py                       # assembles guardrails/sections into the system prompt
  latency.py                       # streaming + timeout + response-length cap
  extraction.py                    # PDF/DOCX -> text, confidence gate
  pii.py                            # local personal-data stripping - no network call
  pii_local.py                     # local spaCy/Presidio name detection, guarded
  guardrails/
    confidentiality.py             # NDA/compensation/offer trigger detection
    global_rules.py                # never-score (reliable) + never-rewrite (heuristic) output checks
    language.py                    # upfront EN/DE choice + per-message re-detection
    dates.py                       # date range extraction, overlap/gap flags
    section_coverage.py            # parses the CV's real headings + categories
  sections/
    education.py
    experience.py
    extracurricular.py
    skills_languages.py            # includes the CEFR-or-plain-label suggestion rule
    other_sections.py              # publications, projects, certifications, awards, volunteering, ...
    jd_alignment.py                # JD-optional flow, structure-only fallback, HSG job categories
```

Two more pieces added after the table below was first written:

- **Proactive section coverage** (`guardrails/section_coverage.py`, wired into
  `prompts.py`'s `PROACTIVE_COVERAGE` block): detects which canonical sections exist
  in THIS student's CV and instructs the bot to work through all of them over the
  conversation — not just react to what's asked — naming the section it's moving to
  each time.
- **End-of-conversation summary** (`prompts.SUMMARY_SYSTEM_PROMPT` /
  `build_summary_messages`, wired into `app.py`): once every detected section has
  been covered, the bot asks (a fixed, code-detected sentence — see
  `prompts.SUMMARY_OFFER_TEXT` / `SUMMARY_OFFER_MARKER`) whether the student wants a
  copy of the conversation. A "yes" triggers a dedicated summarization call
  (strengths identified + what was discussed per section, transcript-only, never
  inventing or drafting CV text) with a `.txt` download button so it's actually
  emailable to Career Services. There's also an always-available "Prepare a summary
  now" button in the sidebar, independent of the bot's own offer, as a safety net.

| Area | Status | Honest caveat |
|---|---|---|
| Never score | Built, reliable | Regex-checked every response, forces regeneration |
| Layout & branding | Built | Single-column HSG-branded page, no sidebar, no per-user API key field, document panel visible on arrival rather than behind an expander. All CSS in `ui.py`. |
| Never rewrite | Built, heuristic | Prompt rule + regex output check on rewritten-bullet-shaped phrasing; not a hard block, still the top candidate for a stronger mechanism |
| PII stripping | Built, fully local | Contact-block removal + local spaCy NER for names + tuned patterns for everything with a reliable shape. `strip_pii()` takes no API client, so the document structurally cannot be sent anywhere before redaction. Person hits are vetoed against the model's own LOCATION/ORGANIZATION reads, and body hits need corroboration, which is what stops "St. Gallen" being treated as a name. Degrades to patterns-only if the models are missing, and says so in the UI. |
| Opening feedback report | Built | Generated once at intake from the redacted text and posted as the bot's first message, in text so it stays questionable. Structure from Career Services' sample: overall impression, format check, what works well, key areas to improve, section-by-section. Held to the same per-section rules as the conversation, assembled from the same modules. |
| CV format check | Built, from the file | Page count, fonts, tables and images come from the document; heading conventionality and bullet glyphs from the text. The "layout" row measures text density and says outright that real whitespace isn't observable. |
| Date gap/overlap flags | Built, approximate | Regex date parsing; feeds the model a flag to ask about, never a verdict — see `guardrails/dates.py` |
| Language: upfront + adaptive | Built | `langdetect`-based, ignores short/ambiguous messages (<15 chars) so a bare "ja"/"ok" doesn't flip the session |
| Latency: streaming + timeout + length cap | Built | The 6s figure is a target the design optimizes for, not something enforceable against a third-party API — see `latency.py` |
| CEFR-or-plain-label suggestion | Built | Prompt-level: the bot is instructed to offer both scales, never assert one |
| JD optional + structure-only fallback | Built | Fallback triggers after one turn without a role; mid-chat role capture is simple keyword matching against HSG's own job categories, not NLU |
| Skill-mismatch handling | Built | Prompt-level only, in `sections/jd_alignment.py` |
| Proactive section coverage | Built, over the CV's real headings | Headings are parsed out of the document itself (verbatim, in order, each mapped to a coaching category) rather than matched against a fixed keyword list, so Publications, Projects, Certifications, Awards, Volunteering, Military Service etc. are now reachable. Parsed headings are validated against the document, so an invented one is dropped. "Has this section been discussed enough" stays the model's judgment on purpose — a turn-counter would transition at the wrong moments. |
| End-of-conversation summary | Built, hybrid | The offer timing is prompt-driven; detecting the offer and generating/downloading the summary is code-driven, same pattern as the confidentiality handover flow |

## 6. What's still open

1. **A harder "never rewrite" mechanism.** Current state (prompt + regex output
   check) is meaningfully better than prompt-only, but a well-worded jailbreak can
   still slip past a regex. The original requirements doc flags this as the rule
   most likely to be tested by a persistent student — worth a second pass once
   there's real usage data on what actually gets through.
2. **Test against real CVs**, not just synthetic ones — in particular the date parser
   (unusual formats, month names beyond EN/DE), the target-role keyword matcher,
   whether the personal-data pass over- or under-redacts on unusual layouts, and
   whether the model paces section transitions sensibly rather than rushing or looping.
3. **HSG-specific activity prompting** (Career Services' second request, 2026-09-01):
   have the bot ask about, and point students toward, HSG's own programmes, clubs,
   certificates and competitions, with the CV section each belongs in. Not built yet —
   the open design question is link durability, since the source list is URL-based.
4. **Stronger name recall.** The small spaCy models miss a name sitting alone on a
   header line often enough that a first-line heuristic backs them up. A larger model
   would improve recall at a real memory cost on Streamlit Community Cloud.
5. **Everything in the "Before you show this to partners" list in README.md** —
   Swiss hosting, a DPA with OpenAI, malware scanning, OCR fallback — is
   infrastructure/legal work, not a code change, and still applies.

## 7. Deployment

Streamlit Community Cloud is the plan for today's partner test — confirmed fine.
See `README.md` in this repo for the exact deploy steps and the standing compliance
caveat (dummy CVs only, no Swiss hosting/DPA yet).
