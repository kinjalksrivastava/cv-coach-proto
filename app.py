"""
Streamlit UI + turn orchestration. No coaching rule text lives here - rules are in
prompts.py / guardrails/ / sections/, and all styling is in ui.py.
"""

import os

import streamlit as st
from openai import OpenAI

import latency
import prompts
import report
import ui
import bullet_review
import cover_letter
import cv_facts
import date_review
import format_check
import severity
import hsg_activities
from extraction import extract_text, MIN_CHARS
from guardrails import confidentiality, global_rules, language, section_coverage
from pii import strip_pii
from sections import jd_alignment

MODEL = "gpt-4.1"

st.set_page_config(
    page_title="CV Coach | University of St.Gallen",
    page_icon=ui.page_icon(),
    layout="centered",
    initial_sidebar_state="collapsed",
)
ui.inject_styles()

# Every word the interface itself says, in both languages. It used to be four
# keys here and the rest hard-coded English, so a student who chose Deutsch got a
# German report inside an English app. Career Services flagged the same mixing
# inside the report; this is the other half of it.
#
# No em dashes anywhere in here. They read as machine-written, and Career
# Services want this to sound like the university, not like a chatbot.
COPY = {
    "en": {
        "unit": "Career Services",
        "title": "CV Coach",
        "subtitle": (
            "Feedback on your own CV, before your Career Services appointment. "
            "It shows you what a reader would stumble over and asks the questions "
            "that help you fix it. It never gives your CV a score and never writes "
            "it for you."
        ),
        "subtitle_letter": (
            "A short first check on your cover letter, before your Career Services "
            "appointment. It looks at whether the letter adds anything your CV does not "
            "already say, and whether it says where you want to go. It never writes it "
            "for you."
        ),
        "chat_placeholder": "Ask about your CV…",
        "mode_cv_title": "Your CV",
        "mode_cv_sub": ("Feedback on structure, content and how the CV reads to a "
                        "recruiter. A target role is optional."),
        "mode_cv_button": "Review my CV",
        "mode_letter_title": "Your cover letter",
        "mode_letter_sub": ("A short first check: does the letter add anything your CV "
                            "does not already say? The job advert or title is needed."),
        "mode_letter_button": "Review my cover letter",
        "ref_cv_title": "Your CV",
        "ref_cv_sub": ("Add it and the single most important check can be made properly: "
                       "does the letter say anything the CV does not already say? Without "
                       "it that can only be guessed at."),
        "letter_title": "Your cover letter",
        "letter_sub": "PDF or Word, up to 10 MB.",
        "role_sub_letter": ("A cover letter is written for one specific role, so this "
                            "one is needed. The advert is best; the job title works."),
        "lang_title": "Language",
        "lang_sub": ("You can switch at any time. Just write in the other language "
                     "and the conversation follows."),
        "cv_title": "Your CV",
        "cv_sub": "PDF or Word, up to 10 MB.",
        "required": "Required",
        "optional": "Optional",
        "upload": "Upload",
        "paste": "Paste text",
        "skip": "Skip",
        "cv_placeholder": "Paste the full text of your CV here",
        "role_title": "Target role",
        "role_sub": ("With one, the feedback is specific to that role. Without one, "
                     "it covers structure and completeness, and your CV still stands "
                     "on its own."),
        "jd_placeholder": "Paste the job description here",
        "role_label": "Or simply name the role or industry",
        "role_placeholder": "e.g. Audit Intern, Sustainability Consulting",
        "start": "Start the session",
        "too_little": ("That is very little text to work with. Please paste the full CV."),
        "spinner": "Reading your CV and writing your feedback report…",
        "spinner_letter": "Reading your cover letter…",
        "panel_title": "What was read from your CV",
        "panel_sub": ("Parsed when you uploaded it. Personal details are removed "
                      "before anything is analysed."),
        "sections_found": "Sections found",
        "no_sections": "no section headings recognised",
        "pii_removed": "Personal details removed",
        "none_detected": "none detected",
        "session": "Session",
        "language_is": "Language",
        "jd_provided": "Job description: provided",
        "role_is": "Target role",
        "role_unset": "Target role: not set yet",
        "summary_button": "Prepare a summary for Career Services",
        "summary_help": "Available at any time, you do not have to wait to be offered one.",
        "download_pdf": "Download the report (PDF)",
        "download_help": "The feedback report from the start of this conversation.",
        "download_text": "Download the report",
        "start_over": "Start over",
        "summary_spinner": "Preparing summary…",
        "download_summary": "Download summary (.txt)",
        "pii_residual": ("**Personal details found late in the check.** These got past "
                         "the normal removal and were caught by the final sweep ({items}). "
                         "They have been removed, but please report this."),
        "pii_spinner": "Removing personal details…",
        "examples_expander": "See what a stronger bullet point looks like",
        "handed_over": "This session has been flagged for a human advisor. "
                       "Coaching is paused here.",
        "pii_degraded": (
            "**Reduced personal-data removal.** The local name-detection model is "
            "not available on this deployment, so only the contact block and "
            "pattern matching ran. A name elsewhere in the document may remain. "
            "Check the list above before using this with a real CV."
        ),
    },
    "de": {
        "unit": "Career Services",
        "title": "CV Coach",
        "subtitle": (
            "Feedback zu deinem Lebenslauf, vor deinem Termin beim Career Services. "
            "Es zeigt dir, worüber ein Lesender stolpern würde, und stellt dir die "
            "Fragen, mit denen du es selbst verbesserst. Es bewertet deinen "
            "Lebenslauf nicht und schreibt ihn nicht für dich."
        ),
        "subtitle_letter": (
            "Ein kurzer erster Check deines Motivationsschreibens, vor deinem Termin "
            "beim Career Services. Geprüft wird, ob das Schreiben etwas sagt, das dein "
            "Lebenslauf nicht schon sagt, und ob klar wird, wohin du willst. Geschrieben "
            "wird es nicht für dich."
        ),
        "chat_placeholder": "Frag mich etwas zu deinem Lebenslauf…",
        "mode_cv_title": "Dein Lebenslauf",
        "mode_cv_sub": ("Feedback zu Aufbau, Inhalt und dazu, wie der Lebenslauf auf "
                        "Recruiter wirkt. Eine Zielposition ist optional."),
        "mode_cv_button": "Lebenslauf prüfen",
        "mode_letter_title": "Dein Motivationsschreiben",
        "mode_letter_sub": ("Ein kurzer erster Check: Sagt das Schreiben etwas, das dein "
                            "Lebenslauf nicht schon sagt? Stellenanzeige oder Titel nötig."),
        "mode_letter_button": "Motivationsschreiben prüfen",
        "ref_cv_title": "Dein Lebenslauf",
        "ref_cv_sub": ("Mit dem Lebenslauf lässt sich die wichtigste Frage sauber prüfen: "
                       "Sagt das Schreiben etwas, das der Lebenslauf nicht schon sagt? "
                       "Ohne ihn bleibt das eine Vermutung."),
        "letter_title": "Dein Motivationsschreiben",
        "letter_sub": "PDF oder Word, bis 10 MB.",
        "role_sub_letter": ("Ein Motivationsschreiben richtet sich an eine konkrete "
                            "Stelle, deshalb ist diese Angabe nötig. Am besten die "
                            "Anzeige, der Stellentitel genügt auch."),
        "lang_title": "Sprache",
        "lang_sub": ("Du kannst jederzeit wechseln. Schreib einfach in der anderen "
                     "Sprache, das Gespräch folgt."),
        "cv_title": "Dein Lebenslauf",
        "cv_sub": "PDF oder Word, bis 10 MB.",
        "required": "Erforderlich",
        "optional": "Optional",
        "upload": "Hochladen",
        "paste": "Text einfügen",
        "skip": "Überspringen",
        "cv_placeholder": "Füge hier den vollständigen Text deines Lebenslaufs ein",
        "role_title": "Zielposition",
        "role_sub": ("Mit einer Angabe ist das Feedback auf diese Rolle zugeschnitten. "
                     "Ohne geht es um Aufbau und Vollständigkeit, und dein Lebenslauf "
                     "steht trotzdem für sich."),
        "jd_placeholder": "Füge hier die Stellenanzeige ein",
        "role_label": "Oder nenne einfach die Rolle oder Branche",
        "role_placeholder": "z.B. Praktikum Audit, Sustainability Consulting",
        "start": "Sitzung starten",
        "too_little": ("Das ist sehr wenig Text. Bitte füge den vollständigen "
                       "Lebenslauf ein."),
        "spinner": "Dein Lebenslauf wird gelesen und dein Feedback geschrieben…",
        "spinner_letter": "Dein Motivationsschreiben wird gelesen…",
        "panel_title": "Was aus deinem Lebenslauf gelesen wurde",
        "panel_sub": ("Beim Hochladen ausgewertet. Persönliche Angaben werden "
                      "entfernt, bevor irgendetwas analysiert wird."),
        "sections_found": "Gefundene Abschnitte",
        "no_sections": "keine Abschnittstitel erkannt",
        "pii_removed": "Entfernte persönliche Angaben",
        "none_detected": "keine erkannt",
        "session": "Sitzung",
        "language_is": "Sprache",
        "jd_provided": "Stellenanzeige: vorhanden",
        "role_is": "Zielposition",
        "role_unset": "Zielposition: noch nicht gesetzt",
        "summary_button": "Zusammenfassung für Career Services vorbereiten",
        "summary_help": ("Jederzeit verfügbar, du musst nicht warten, bis sie "
                         "angeboten wird."),
        "download_pdf": "Report herunterladen (PDF)",
        "download_help": "Der Feedback-Report vom Beginn dieses Gesprächs.",
        "download_text": "Report herunterladen",
        "start_over": "Neu beginnen",
        "summary_spinner": "Zusammenfassung wird vorbereitet…",
        "download_summary": "Zusammenfassung herunterladen (.txt)",
        "pii_residual": ("**Persönliche Angaben erst spät erkannt.** Diese sind durch die "
                         "normale Entfernung gerutscht und wurden erst im letzten Durchgang "
                         "gefunden ({items}). Sie wurden entfernt, bitte melde das aber."),
        "pii_spinner": "Persönliche Angaben werden entfernt…",
        "examples_expander": "So sieht ein stärkerer Bullet Point aus",
        "handed_over": "Diese Sitzung wurde für eine Beratungsperson markiert. "
                       "Das Coaching pausiert hier.",
        "pii_degraded": (
            "**Eingeschränkte Entfernung personenbezogener Daten.** Das lokale Modell "
            "zur Namenserkennung ist in diesem Deployment nicht verfügbar. Es liefen "
            "nur die Kontaktblock-Entfernung und die Mustererkennung, ein Name an "
            "anderer Stelle im Dokument kann also erhalten bleiben. Prüfe die Liste "
            "oben, bevor du damit einen echten Lebenslauf verarbeitest."
        ),
    },
}


def _configured_key() -> str | None:
    """
    The shared key, configured once so anyone with the app's link can use it with
    zero setup. Streamlit secrets first (.streamlit/secrets.toml locally, or the
    Secrets box in Streamlit Community Cloud), then the environment. Wrapped in
    try/except because st.secrets raises when no secrets file exists at all.
    """
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY")


def get_client() -> OpenAI | None:
    api_key = _configured_key()
    return OpenAI(api_key=api_key) if api_key else None


def init_state():
    defaults = {
        "cv_text": None,
        "cv_redactions": [],
        "mode": None,          # "cv" or "letter", chosen on the first screen
        "letter_report": None,
        "letter_pdf": None,
        "pii_degraded": False,
        "pii_residual": [],
        "format_rows": [],
        "report_text": None,
        "report_pdf": None,
        "show_bullet_examples": False,
        "jd_text": None,
        "jd_redactions": [],
        "target_role_hint": "",
        "target_role_followup_count": 0,
        "structure_only_mode": False,
        "date_findings": [],
        "sections_detected": [],
        "summary_offer_pending": False,
        "language_pref": "en",       # chosen upfront
        "effective_language": "en",  # may drift from the pref during the chat
        "messages": [],
        "pending_handover_reason": None,
        "handed_over": False,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def reset_session():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    init_state()


init_state()

# The language radio lives further down the intake screen, but the masthead and
# the title above it have to be rendered in the chosen language on the SAME run.
# Reading the widget's own key here does that; rendering first and assigning
# after the radio left the page one rerun behind, showing the previous choice.
if st.session_state["cv_text"] is None and "lang_choice" in st.session_state:
    st.session_state["language_pref"] = (
        "en" if st.session_state["lang_choice"] == "English" else "de"
    )
    st.session_state["effective_language"] = st.session_state["language_pref"]

lang = st.session_state["effective_language"]
copy = COPY[lang]

ui.masthead(lang, copy["unit"])

client = get_client()
if client is None:
    ui.title_block(copy["title"], copy["subtitle"])
    st.error(
        "This app isn't configured with an API key yet. Set `OPENAI_API_KEY` in "
        "`.streamlit/secrets.toml` locally, or in the app's **Settings → Secrets** on "
        "Streamlit Community Cloud. See README.md.",
        icon="⚙️",
    )
    st.stop()


# --- the document panel: what was read out of the CV, visible by default ------
def document_panel():
    with ui.card("panel"):
        ui.card_head(
            copy["panel_title"], copy["panel_sub"],
        )
        ui.chips(
            copy["sections_found"],
            section_coverage.headings(st.session_state["sections_detected"]),
            empty_text=copy["no_sections"],
        )
        ui.chips(
            copy["pii_removed"],
            st.session_state["cv_redactions"],
            kind="",
            empty_text=copy["none_detected"],
        )
        # Timeline notes used to sit here, at the top of the screen, in wording
        # written for the model rather than the student. They now close the
        # report instead, where a reader meets them after the substance.
        context_bits = [f'{copy["language_is"]}: {language.SUPPORTED[lang]}']
        if st.session_state["jd_text"]:
            context_bits.append(copy["jd_provided"])
        elif st.session_state["target_role_hint"]:
            context_bits.append(
                f'{copy["role_is"]}: {st.session_state["target_role_hint"]}')
        else:
            context_bits.append(copy["role_unset"])
        ui.chips(copy["session"], context_bits, kind="")
        if st.session_state["pii_residual"]:
            st.warning(copy["pii_residual"].format(
                items=", ".join(st.session_state["pii_residual"])), icon="⚠️")
        if st.session_state["pii_degraded"]:
            # Loud rather than quiet on purpose: without the local name model, the
            # contact block and the patterns still run but a name in the body of
            # the CV can survive. Anyone demonstrating this needs to know.
            st.warning(copy["pii_degraded"], icon="⚠️")


# --- Step 0: which document ---------------------------------------------------
# Two separate jobs with two separate standards. A CV is judged on what it shows;
# a cover letter is judged on whether it adds anything the CV does not. Career
# Services asked for them to be chosen up front rather than inferred.
if st.session_state["mode"] is None:
    ui.title_block(copy["title"], copy["subtitle"])
    left, right = st.columns(2, gap="medium")
    with left:
        with ui.card("mode_cv"):
            ui.card_head(copy["mode_cv_title"], copy["mode_cv_sub"])
            if st.button(copy["mode_cv_button"], type="primary", use_container_width=True):
                st.session_state["mode"] = "cv"
                st.rerun()
    with right:
        with ui.card("mode_letter"):
            ui.card_head(copy["mode_letter_title"], copy["mode_letter_sub"])
            if st.button(copy["mode_letter_button"], use_container_width=True):
                st.session_state["mode"] = "letter"
                st.rerun()
    st.stop()


# --- Step 1: document intake -------------------------------------------------
if st.session_state["cv_text"] is None:
    is_letter = st.session_state["mode"] == "letter"
    ui.title_block(copy["title"],
                   copy["subtitle_letter"] if is_letter else copy["subtitle"])

    with ui.card("lang"):
        ui.card_head(copy["lang_title"], copy["lang_sub"])
        st.radio(
            "Language", ["English", "Deutsch"], horizontal=True,
            label_visibility="collapsed", key="lang_choice",
        )

    left, right = st.columns(2, gap="medium")

    with left:
        with ui.card("cv"):
            ui.card_head(copy["letter_title"] if is_letter else copy["cv_title"],
                         copy["letter_sub"] if is_letter else copy["cv_sub"],
                         copy["required"], "req")
            cv_options = [copy["upload"], copy["paste"]]
            cv_mode = cv_options.index(st.radio(
                "CV input", cv_options, horizontal=True,
                label_visibility="collapsed", key="cv_mode",
            ))
            cv_file, cv_pasted = None, ""
            if cv_mode == 0:
                cv_file = st.file_uploader(
                    "CV", type=["pdf", "docx"], key="cv_upload", label_visibility="collapsed"
                )
            else:
                cv_pasted = st.text_area(
                    "CV text", height=180, key="cv_paste", label_visibility="collapsed",
                    placeholder=copy["cv_placeholder"],
                )

    with right:
        with ui.card("role"):
            # A cover letter is written for one specific role, so the advert or at
            # least a job title is required here - Career Services were explicit.
            # A CV stands on its own, so it stays optional there.
            ui.card_head(
                copy["role_title"],
                copy["role_sub_letter"] if is_letter else copy["role_sub"],
                copy["required"] if is_letter else copy["optional"],
                "req" if is_letter else "opt")
            # No "Skip" when the role is required - offering a choice the form
            # then refuses to accept is just a dead end.
            jd_options = ([copy["upload"], copy["paste"]] if is_letter
                          else [copy["skip"], copy["upload"], copy["paste"]])
            chosen = jd_options.index(st.radio(
                "Job description", jd_options, horizontal=True,
                label_visibility="collapsed", key="jd_mode",
            ))
            jd_mode = chosen + 1 if is_letter else chosen
            jd_file, jd_pasted = None, ""
            if jd_mode == 1:
                jd_file = st.file_uploader(
                    "Job description", type=["pdf", "docx"], key="jd_upload",
                    label_visibility="collapsed",
                )
            elif jd_mode == 2:
                jd_pasted = st.text_area(
                    "Job description text", height=180, key="jd_paste",
                    label_visibility="collapsed",
                    placeholder=copy["jd_placeholder"],
                )
            target_hint = st.text_input(
                copy["role_label"], placeholder=copy["role_placeholder"],
            )

    # In cover-letter mode, the CV itself is worth having: Career Services' most
    # important check is whether the letter adds value BEYOND the CV, and without
    # the CV that can only be inferred from whether the letter reads like a
    # chronology. Optional, because a student may not have it to hand.
    ref_file, ref_pasted = None, ""
    if is_letter:
        with ui.card("refcv"):
            ui.card_head(copy["ref_cv_title"], copy["ref_cv_sub"], copy["optional"], "opt")
            ref_options = [copy["skip"], copy["upload"], copy["paste"]]
            ref_mode = ref_options.index(st.radio(
                "Reference CV", ref_options, horizontal=True,
                label_visibility="collapsed", key="ref_mode",
            ))
            if ref_mode == 1:
                ref_file = st.file_uploader(
                    "Reference CV", type=["pdf", "docx"], key="ref_upload",
                    label_visibility="collapsed")
            elif ref_mode == 2:
                ref_pasted = st.text_area(
                    "Reference CV text", height=150, key="ref_paste",
                    label_visibility="collapsed", placeholder=copy["cv_placeholder"])

    have_doc = cv_file is not None or bool(cv_pasted.strip())
    have_target = (jd_file is not None or bool(jd_pasted.strip())
                   or bool(target_hint.strip()))
    ready = have_doc and (have_target or not is_letter)
    if is_letter and have_doc and not have_target:
        st.info(cover_letter.STRINGS[st.session_state["language_pref"]]["needs_jd"], icon="📌")
    if st.button(copy["start"], type="primary", disabled=not ready):
        if cv_file is not None:
            cv_result = extract_text(cv_file.getvalue(), cv_file.name)
            if not cv_result.ok:
                st.error(cv_result.error, icon="📄")
                st.stop()
            cv_raw, cv_meta = cv_result.text, cv_result.meta
        else:
            if len(cv_pasted.strip()) < MIN_CHARS:
                st.error(copy["too_little"], icon="📄")
                st.stop()
            cv_raw = cv_pasted
            # Pasted text carries no file to measure, so the format check will
            # report what it can and say what it can't.
            cv_meta = {"source": "pasted", "page_count": None, "fonts": [],
                       "image_count": 0, "table_count": 0, "char_count": len(cv_raw.strip())}

        jd_raw = ""
        if jd_file is not None:
            jd_result = extract_text(jd_file.getvalue(), jd_file.name)
            if jd_result.ok:
                jd_raw = jd_result.text
            else:
                st.warning(f"Job description could not be used: {jd_result.error}")
        elif jd_pasted.strip():
            jd_raw = jd_pasted

        target_role = target_hint.strip()

        # --- personal data comes off FIRST, locally, before anything leaves this
        # machine. Nothing below this point ever sees the original document. ---
        cv_language = language.detect_message_language(cv_raw) or st.session_state["language_pref"]
        with st.spinner(copy["pii_spinner"]):
            cv_clean = strip_pii(cv_raw, cv_language)
            jd_clean = strip_pii(jd_raw, cv_language) if jd_raw.strip() else None

        cv_text = cv_clean["text"]
        st.session_state["cv_text"] = cv_text
        st.session_state["cv_redactions"] = cv_clean["redactions"]
        st.session_state["pii_degraded"] = cv_clean["degraded"]
        # Anything here got past every removal layer and was caught only by the
        # final verification sweep. It is redacted either way, but it means a
        # layer is not doing its job and someone should look.
        st.session_state["pii_residual"] = cv_clean.get("residual") or []
        if jd_clean:
            st.session_state["jd_text"] = jd_clean["text"]
            st.session_state["jd_redactions"] = jd_clean["redactions"]
        st.session_state["target_role_hint"] = target_role

        # --- only now, on the redacted text, the model calls. The section parse
        # has to finish first: the measured facts are computed against the parsed
        # sections, and the ranked issues are computed from those facts. The model
        # writes the report from that, rather than deciding for itself what is
        # wrong with the CV. ---
        lang_code = st.session_state["language_pref"]

        # --- the cover letter path. A different document with a different job,
        # judged against Career Services' cover-letter rules rather than the CV
        # prioritisation list, and deliberately much shorter: "identify whether
        # the cover letter is doing its job, not replace a coaching appointment".
        if st.session_state["mode"] == "letter":
            letter_strings = cover_letter.STRINGS[lang_code]
            # The reference CV goes through exactly the same redaction as every
            # other document before anything sees it.
            reference_cv = ""
            if ref_file is not None:
                parsed = extract_text(ref_file.getvalue(), ref_file.name)
                if parsed.ok:
                    reference_cv = strip_pii(parsed.text, cv_language)["text"]
            elif ref_pasted.strip():
                reference_cv = strip_pii(ref_pasted, cv_language)["text"]
            with st.spinner(copy["spinner_letter"]):
                letter_facts = cover_letter.analyse(
                    cv_text, st.session_state["jd_text"] or "", target_role, reference_cv)
                letter_data = cover_letter.generate(
                    client, MODEL, cv_text, st.session_state["jd_text"] or "",
                    target_role, letter_facts, language.SUPPORTED[lang_code])
            if letter_data:
                st.session_state["letter_report"] = cover_letter.render_markdown(
                    letter_data, letter_facts, letter_strings)
                st.session_state["letter_pdf"] = cover_letter.to_pdf(
                    letter_data, letter_facts, letter_strings)
                opening = st.session_state["letter_report"]
            else:
                opening = letter_strings["failure"]
            st.session_state["messages"].append({"role": "assistant", "content": opening})
            st.rerun()

        with st.spinner(copy["spinner"]):
            sections = section_coverage.detect_sections(cv_text, client, MODEL)
            st.session_state["sections_detected"] = sections
            # Whether a bullet describes a duty or a contribution is a judgement
            # about language, not a fact about the document, so the model makes
            # it - held to the same section rules the conversation uses. The
            # phrase list inside cv_facts stays as the floor, so a failed or slow
            # call costs the extra findings and nothing else.
            def review_bullets(items):
                return bullet_review.review(
                    client, MODEL, items, report.SECTION_RULES)

            # Reading a date in an unfamiliar format is parsing, and the pattern
            # list keeps losing formats silently. The model reads; the gap and
            # overlap arithmetic stays in code.
            def read_dates(document):
                return date_review.read(client, MODEL, document)

            facts = cv_facts.analyse(cv_text, cv_meta, sections,
                                     st.session_state["jd_text"], lang_code,
                                     review_bullets, read_dates)
            st.session_state["date_findings"] = facts["date_findings"]
            st.session_state["format_rows"] = format_check.run(
                cv_text, cv_meta, facts, lang_code)
            ranked = severity.assess(facts, target_role)
            report_data = report.generate(
                client, MODEL, cv_text, st.session_state["jd_text"], target_role,
                st.session_state["format_rows"], facts, ranked,
                language.SUPPORTED[lang_code],
            )

        if report_data:
            strings = dict(report.STRINGS[lang_code])
            strings["criteria_note"] = format_check.criteria_note(lang_code)
            notes = report.deterministic_notes(facts, lang_code)
            # Chosen in code, not by the model: the links have to be the real ones
            # from hsg_activities, and a model asked for a URL will invent a
            # plausible-looking dead one.
            # Ordered by what this CV actually needs: the sections the report is
            # unhappy about first, then the target role, then the standing picks
            # so the section is never empty.
            hsg_picks = hsg_activities.closing_suggestions(
                target_role, cv_text,
                section_status=ranked["section_status"],
                missing_sections=facts.get("missing_report_sections"),
                categories={s["heading"]: s["category"] for s in sections},
            )
            report_text = report.render_markdown(
                report_data, st.session_state["format_rows"], strings,
                facts["date_findings"], notes, hsg_picks, ranked["section_status"],
            )
            st.session_state["report_text"] = report_text
            st.session_state["report_pdf"] = report.to_pdf(
                report_data, st.session_state["format_rows"], strings,
                facts["date_findings"], notes, hsg_picks, ranked["section_status"],
            )
            st.session_state["show_bullet_examples"] = True
        else:
            report_text = report.FAILURE_TEXT[lang_code]
        st.session_state["messages"].append({"role": "assistant", "content": report_text})
        st.rerun()

    st.stop()

# --- Step 2: chat -------------------------------------------------------------
ui.title_block(copy["title"], compact=True)
if st.session_state["mode"] != "letter":
    document_panel()

target_role_known = bool(st.session_state["jd_text"] or st.session_state["target_role_hint"])

col_summary, col_report, col_reset = st.columns([3, 2, 2], gap="small")
with col_summary:
    summary_clicked = st.button(
        copy["summary_button"],
        disabled=len(st.session_state["messages"]) < 3,
        help=copy["summary_help"],
        use_container_width=True,
    )
with col_report:
    # PDF by default - a reviewer could not open the markdown version at all.
    # The text download stays as the fallback if reportlab isn't installed.
    if st.session_state["letter_pdf"]:
        st.download_button(
            copy["download_pdf"], data=st.session_state["letter_pdf"],
            file_name="cover_letter_feedback.pdf", mime="application/pdf",
            help=copy["download_help"], use_container_width=True,
            key="letter_download_pdf",
        )
    elif st.session_state["report_pdf"]:
        st.download_button(
            copy["download_pdf"],
            data=st.session_state["report_pdf"],
            file_name="cv_feedback_report.pdf",
            mime="application/pdf",
            help=copy["download_help"],
            use_container_width=True,
            key="report_download_pdf",
        )
    elif st.session_state["report_text"]:
        st.download_button(
            copy["download_text"],
            data=st.session_state["report_text"],
            file_name="cv_feedback_report.md",
            mime="text/markdown",
            use_container_width=True,
            key="report_download",
        )
with col_reset:
    if st.button(copy["start_over"], use_container_width=True):
        reset_session()
        st.rerun()

if summary_clicked:
    summary_messages = prompts.build_summary_messages(
        st.session_state["messages"], st.session_state["sections_detected"],
        lang, language.SUPPORTED[lang],
    )
    with st.spinner(copy["summary_spinner"]):
        manual_summary_text = latency.stream_response(
            client, MODEL, summary_messages, lambda _: None,
            max_tokens=latency.SUMMARY_MAX_TOKENS, timeout=latency.SUMMARY_TIMEOUT_SECONDS,
        )
    with ui.card("summary"):
        st.markdown(manual_summary_text)
        st.download_button(
            copy["download_summary"],
            data=manual_summary_text, file_name="cv_coach_summary.txt", mime="text/plain",
            key="manual_summary_download",
        )

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# The weak-vs-strong bullet table, on demand rather than inline at the top of the
# report. Career Services found it confusing where it was - it arrived before the
# student had been told anything about their bullets - and wanted it behind a
# click, at the point bullets are actually raised.
if st.session_state["show_bullet_examples"]:
    with st.expander(copy["examples_expander"]):
        strings = dict(report.STRINGS[st.session_state["effective_language"]])
        st.markdown(report.bullet_examples_markdown(strings))

if st.session_state["handed_over"]:
    st.info(copy["handed_over"])
    st.stop()

user_input = st.chat_input(copy["chat_placeholder"])

if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # --- language: may drift from the stated preference (resolved early - the
    # summary-generation branch below needs it too) ---
    st.session_state["effective_language"] = language.resolve_effective_language(
        st.session_state["language_pref"], st.session_state["effective_language"], user_input
    )
    lang_code = st.session_state["effective_language"]
    lang_name = language.SUPPORTED[lang_code]

    # --- end-of-conversation summary offer: runs BEFORE the model, code-driven
    # like the handover flow, so "yes" reliably produces a downloadable summary
    # instead of hoping the model remembers to attach one ---
    if st.session_state["summary_offer_pending"]:
        st.session_state["summary_offer_pending"] = False
        if prompts.is_affirmative(user_input):
            summary_messages = prompts.build_summary_messages(
                st.session_state["messages"], st.session_state["sections_detected"],
                lang_code, lang_name,
            )
            with st.chat_message("assistant"):
                placeholder = st.empty()

                def on_delta(text_so_far: str):
                    placeholder.markdown(text_so_far + "▌")

                summary_text = latency.stream_response(
                    client, MODEL, summary_messages, on_delta,
                    max_tokens=latency.SUMMARY_MAX_TOKENS, timeout=latency.SUMMARY_TIMEOUT_SECONDS,
                )
                placeholder.markdown(summary_text)
                st.download_button(
                    "Download summary (.txt)",
                    data=summary_text, file_name="cv_coach_summary.txt", mime="text/plain",
                )
            st.session_state["messages"].append({"role": "assistant", "content": summary_text})
            st.stop()
        # else: student said something other than yes - fall through and answer
        # it normally below, rather than forcing a canned decline.

    # --- confidentiality / handover check (runs BEFORE the model) ---
    if st.session_state["pending_handover_reason"]:
        reason = st.session_state["pending_handover_reason"]
        if user_input.strip().lower() in ("yes", "y", "ja", "confirm", "confirmed"):
            summary = f"Topic flagged: {reason}. Last message: \"{user_input}\""
            reply = prompts.HANDOVER_SUMMARY_TEMPLATE.format(summary=summary)
            st.session_state["handed_over"] = True
        else:
            reply = (
                "Understood, no handover. I'll keep helping with anything else on "
                "your CV that doesn't touch that topic."
            )
            st.session_state["pending_handover_reason"] = None
        st.session_state["messages"].append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)
        st.rerun()

    triggers = confidentiality.detect_confidentiality_trigger(user_input)
    if triggers:
        reason = ", ".join(triggers)
        st.session_state["pending_handover_reason"] = reason
        reply = prompts.HANDOVER_CONFIRM_TEMPLATE.format(reason=reason)
        st.session_state["messages"].append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)
        st.stop()

    # --- target role: try to capture it from free text if not yet known ---
    if not target_role_known:
        matched = jd_alignment.detect_target_role_mention(user_input)
        if matched:
            st.session_state["target_role_hint"] = matched
            target_role_known = True

    if not target_role_known:
        st.session_state["target_role_followup_count"] += 1
        if st.session_state["target_role_followup_count"] > 1:
            st.session_state["structure_only_mode"] = True
    else:
        st.session_state["structure_only_mode"] = False

    # --- build the model call ---
    context_block = prompts.build_context_block(
        st.session_state["cv_text"],
        st.session_state["jd_text"],
        target_role_known,
        st.session_state["structure_only_mode"],
        lang_code,
        lang_name,
        [f["text"] for f in st.session_state["date_findings"]],
        st.session_state["sections_detected"],
    )
    # In cover-letter mode the conversation is held to Career Services' cover
    # letter rules, not the CV prioritisation list: a different document with a
    # different job, and a much narrower remit.
    api_messages = [{"role": "system", "content": prompts.SYSTEM_PROMPT}]
    if st.session_state["mode"] == "letter":
        api_messages.append({"role": "system", "content": cover_letter.RULES})
    api_messages.append({"role": "system", "content": context_block})
    if st.session_state["target_role_hint"]:
        api_messages.append(
            {"role": "system",
             "content": f"Student-stated target role/industry: {st.session_state['target_role_hint']}"}
        )
    if st.session_state["structure_only_mode"]:
        api_messages.append({"role": "system", "content": prompts.STRUCTURE_ONLY_NOTICE})
    if global_rules.contains_rewrite_pressure(user_input):
        api_messages.append({"role": "system", "content": global_rules.REWRITE_PRESSURE_REMINDER})

    for m in st.session_state["messages"]:
        api_messages.append({"role": m["role"], "content": m["content"]})

    with st.chat_message("assistant"):
        placeholder = st.empty()

        def on_delta(text_so_far: str):
            placeholder.markdown(text_so_far + "▌")

        reply_text = latency.stream_response(client, MODEL, api_messages, on_delta)

        # --- output guardrails: never score, never rewrite (heuristic) ---
        retry_reminder = None
        if global_rules.output_score_check(reply_text):
            retry_reminder = global_rules.SCORE_RETRY_REMINDER
        elif global_rules.output_rewrite_check(reply_text):
            retry_reminder = global_rules.REWRITE_RETRY_REMINDER

        if retry_reminder:
            retry_messages = api_messages + [
                {"role": "assistant", "content": reply_text},
                {"role": "system", "content": retry_reminder},
            ]
            reply_text = latency.stream_response(client, MODEL, retry_messages, on_delta)
            if global_rules.output_score_check(reply_text) or global_rules.output_rewrite_check(reply_text):
                reply_text += "\n\n⚠️ *Guardrail note: this response may still need review.*"

        placeholder.markdown(reply_text)

    st.session_state["messages"].append({"role": "assistant", "content": reply_text})

    # --- did the bot just make the end-of-conversation summary offer? ---
    if prompts.SUMMARY_OFFER_MARKER in reply_text:
        st.session_state["summary_offer_pending"] = True
    st.rerun()
