# HSG CV Coach — prototype

Built from `cv_coach_requirements.docx`, `tech_requirements.docx` (10 user stories +
edge cases), and `HSG_Top_Job_Categories.docx`. Chat UI in Streamlit, GPT-4.1 as the
model, streamed responses, guardrails enforced in code where code can enforce them.

See `PROJECT_SPEC.md` for the full rule-by-rule spec (what each CV section's
guardrails are and where they came from) — this file is about the code.

## Before you show this to partners — read this

Good for validating the **conversation logic and guardrails**. **Not** the compliant
system described in the requirements doc:

- **Hosting is not Swiss, no DPA with OpenAI.** Use dummy/synthetic CVs, not real
  student documents, until both are in place.
- **Personal-data stripping is now hybrid, and still not certified.** A deterministic
  layer (email, phone, profile links, IBAN, ID numbers, date of birth, nationality,
  civil status, postal address) plus a model layer that returns verbatim spans to
  remove — which is what finally makes names, free-form addresses and referee details
  work, since a regex cannot tell "Anna Meier" from "Nestlé S.A.". The model only ever
  names spans; `pii.py` does the replacement itself with string operations, so no
  generated text can enter the document.
- **The model layer sends the RAW document to OpenAI in order to find the PII in it.**
  Previously only regex-redacted text left the machine. Under the standing posture
  below (dummy CVs, no DPA, no Swiss hosting) this isn't a new class of exposure — the
  document was already being sent for coaching — but it is a real change. `strip_pii()`
  still works with no client, so a fully local deployment stays possible.
- **Date-gap/overlap detection is regex-based and approximate** — see `guardrails/dates.py`
  docstring. It's a flag for the bot to ask about, never a verdict, by design — but the
  underlying date parsing itself can miss unusual formats or misread an ambiguous one.
- **No malware scanning, no OCR fallback, no layout-aware extraction.** A scanned CV
  correctly hits the confidence gate and asks for re-upload rather than failing silently.
- **Session storage is in-process memory** (Streamlit's `session_state`), not Redis —
  functionally ephemeral, not the same infrastructure as the target architecture.
- **"Never rewrite" has two layers now, still not a hard block.** The system prompt
  states it as a hard rule, and `guardrails/global_rules.py` regex-checks every
  response for rewritten-bullet-shaped phrasing and forces one regeneration if it
  fires. Both are heuristics — a well-worded jailbreak can still slip past a regex.
  Flagged in the original requirements doc as the rule most likely to be tested by a
  persistent student; still the top candidate for a harder mechanism later.
- **"Never score" is fully code-enforced** — regex-checked on every response, forces
  a regeneration if it fires.
- **The 6-second latency budget is a target, not a guarantee.** A third-party model's
  total generation time isn't something a client can hard-cap without risking a
  truncated answer. What's actually built: streaming (so the student sees output
  almost immediately), a request timeout with a graceful fallback message, and a
  response length cap that keeps both actual and perceived latency down. See
  `latency.py`'s docstring for the honest version of this.
- **Target-role capture from free chat is a simple keyword match**
  (`sections/jd_alignment.py`, built from HSG's own job-category list), not NLU. Safe
  on both failure modes: a miss just means the bot asks again or falls into
  structure-only mode; a false positive is easy for the student to correct.
- **"When has a section been covered enough to move on" is left to the model.** Section
  *parsing* (what exists in this CV) is a constrained model call whose output is
  validated against the document; the pacing judgment isn't — a rigid
  turn-counter would transition at the wrong moments as often as the right ones. Worth
  watching in testing: does it move on too fast, or loop on one section too long.

## What's implemented

- CV + job description intake, **either upload (PDF/DOCX) or paste text**, JD fully
  optional — the CV can stand alone (`app.py` intake step)
- Session language chosen upfront (English/Deutsch), but re-detected per message and
  overridden if the student actually writes in the other language
  (`guardrails/language.py`)
- Personal-data stripping in two layers — deterministic patterns plus model-driven
  verbatim span detection — covering name, email, phone, postal address, LinkedIn /
  GitHub / personal links, date and place of birth, nationality, civil status,
  ID/matriculation numbers, bank details and referee details; photo excluded by
  construction, since only text is ever extracted (`pii.py`)
- Date range extraction with overlap/gap flags fed to the model as things to ask
  about, never as conclusions (`guardrails/dates.py`)
- Confidentiality/handover detection, pre-model (`guardrails/confidentiality.py`)
- Output guardrails: never-score (reliable, code-checked) and never-rewrite
  (heuristic, code-checked) — both force one regeneration if triggered
  (`guardrails/global_rules.py`)
- Target-role-first gate, with a structure-only fallback after one follow-up if no
  JD/role arrives, and best-effort mid-chat capture of a stated target industry
  (`sections/jd_alignment.py`)
- Per-CV-section rules as separate, individually readable modules — Education,
  Experience, Extracurricular & Interests, Skills & Languages, JD Alignment
  (`sections/*.py`), assembled into one system prompt by `prompts.py`
- **Proactive section coverage over the CV's real headings** — the document's own
  section headings are parsed out of it (not matched against a fixed keyword list),
  kept verbatim and in document order, and each mapped to a coaching category. So a CV
  with `SELECTED PUBLICATIONS`, `IT & TOOLS`, `Berufserfahrung` or `MILITARY SERVICE`
  gets coached on all of them, in its own words. The keyword scan survives as the
  offline fallback (`guardrails/section_coverage.py`, rules in `sections/other_sections.py`)
- **End-of-conversation summary** — once every detected section is covered, the bot
  offers a copy of the conversation (strengths + what was discussed per section,
  never inventing or drafting text) as a downloadable `.txt` to bring to Career
  Services. Also available at any time from a button above the conversation,
  independent of the bot's own offer (`prompts.py` summary functions, wired in `app.py`)
- Streamed responses with a request timeout and response-length cap aimed at the
  <6s-per-turn target (`latency.py`)

## Configure the shared API key

The app is built so you set the key once and everyone with the link just uses it —
no one else has to paste anything. Set it in `.streamlit/secrets.toml`, not in
`app.py` — that file is gitignored, so the real key never ends up in git history
(a "private" GitHub repo isn't a strong enough guarantee once collaborators, forks,
or a visibility change enter the picture, and GitHub's own secret scanning will
flag a key committed in plain source anyway).

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit .streamlit/secrets.toml and replace the placeholder with the real key
```

That's it locally — `app.py` reads it automatically via `st.secrets`. There is no
per-user key field in the interface: the key is configured once and everyone who opens
the link uses it.

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Try it on your own CV before pushing anywhere.

## Deploy — Streamlit Community Cloud

1. Push this folder to a GitHub repo (`.streamlit/secrets.toml` won't be included —
   it's gitignored; `.streamlit/secrets.toml.example` will be, which is fine, it has
   no real key in it).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in, "New app".
3. Point it at the repo, branch, and `app.py`.
4. In the app's **Settings → Secrets**, paste the same line:
   ```toml
   OPENAI_API_KEY = "sk-..."
   ```
   This is the actual "hardcode it on my end" step — once it's set here, anyone who
   opens the app's link uses it with zero setup on their side.
5. Deploy — shareable `*.streamlit.app` URL in about 2 minutes.

## Files

```
app.py                          # Streamlit UI + turn orchestration only, no rule text
ui.py                            # stylesheet, HSG masthead, cards/chips - all styling
assets/                          # University of St.Gallen logo (EN/DE) + favicon
prompts.py                       # assembles guardrails/sections into the system prompt
latency.py                       # streaming + timeout + response-length cap
extraction.py                    # PDF/DOCX -> text, confidence gate
pii.py                            # regex PII stripping
guardrails/
  confidentiality.py             # NDA/compensation/offer trigger detection
  global_rules.py                # never-score, never-rewrite (heuristic), rewrite-pressure detection
  language.py                    # upfront choice + per-message re-detection
  dates.py                       # date range extraction, overlap/gap flags
  section_coverage.py            # parses the CV's real section headings + categories
sections/
  education.py                   # grades, thesis, exchange semester, date flags
  experience.py                  # What/How/Why/Result, quantification, year-of-study, return offers
  extracurricular.py             # single-word interests, soft-skill evidence
  skills_languages.py            # CEFR/plain-label suggestion, tool-use evidence
  other_sections.py              # publications, projects, certifications, awards, volunteering, ...
  jd_alignment.py                # JD-optional flow, structure-only fallback, HSG job categories
requirements.txt
PROJECT_SPEC.md                  # full rule-by-rule spec with story references
.streamlit/
  config.toml                    # light theme in HSG corporate colours
  secrets.toml.example           # template - copy to secrets.toml and add the real key
  secrets.toml                   # your real key goes here - gitignored, never committed
.gitignore                       # excludes secrets.toml and Python cache from git
```
