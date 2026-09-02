"""
Streamlit UI + turn orchestration. No coaching rule text lives here - rules are in
prompts.py / guardrails/ / sections/, and all styling is in ui.py.
"""

import os
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from openai import OpenAI

import latency
import hsg_activities
import prompts
import report
import ui
import format_check
from extraction import extract_text, MIN_CHARS
from guardrails import confidentiality, dates, global_rules, language, section_coverage
from pii import strip_pii
from sections import jd_alignment

MODEL = "gpt-4.1"

st.set_page_config(
    page_title="CV Coach — University of St.Gallen",
    page_icon=ui.page_icon(),
    layout="centered",
    initial_sidebar_state="collapsed",
)
ui.inject_styles()

COPY = {
    "en": {
        "unit": "Career Services",
        "title": "CV Coach",
        "subtitle": (
            "A guided conversation to help you strengthen your own CV before your "
            "Career Services appointment. It asks questions — it never scores your "
            "CV and never writes it for you."
        ),
        "chat_placeholder": "Ask about your CV…",
    },
    "de": {
        "unit": "Career Services",
        "title": "CV Coach",
        "subtitle": (
            "Ein geführtes Gespräch, das dir hilft, deinen Lebenslauf vor dem Termin "
            "beim Career Services selbst zu verbessern. Es stellt Fragen — es bewertet "
            "deinen Lebenslauf nicht und schreibt ihn nicht für dich."
        ),
        "chat_placeholder": "Frag mich etwas zu deinem Lebenslauf…",
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
        "pii_degraded": False,
        "format_rows": [],
        "report_text": None,
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
            "What I read from your CV",
            "Parsed automatically when you uploaded it. Personal details are removed "
            "before anything is analysed.",
        )
        ui.chips(
            "Sections found",
            section_coverage.headings(st.session_state["sections_detected"]),
            empty_text="no section headings recognised",
        )
        ui.chips(
            "Personal details removed",
            st.session_state["cv_redactions"],
            kind="",
            empty_text="none detected",
        )
        if st.session_state["date_findings"]:
            ui.notes("Dates worth talking about", st.session_state["date_findings"])
        context_bits = [f"Language: {language.SUPPORTED[lang]}"]
        if st.session_state["jd_text"]:
            context_bits.append("Job description: provided")
        elif st.session_state["target_role_hint"]:
            context_bits.append(f"Target role: {st.session_state['target_role_hint']}")
        else:
            context_bits.append("Target role: not set yet")
        ui.chips("Session", context_bits, kind="")
        if st.session_state["pii_degraded"]:
            # Loud rather than quiet on purpose: without the local name model, the
            # contact block and the patterns still run but a name in the body of
            # the CV can survive. Anyone demonstrating this needs to know.
            st.warning(
                "**Reduced personal-data removal.** The local name-detection model "
                "isn't available on this deployment, so only the contact block and "
                "pattern matching ran — a name elsewhere in the document may remain. "
                "Check the list above before using this with a real CV.",
                icon="⚠️",
            )


# --- Step 1: document intake -------------------------------------------------
if st.session_state["cv_text"] is None:
    ui.title_block(copy["title"], copy["subtitle"])

    with ui.card("lang"):
        ui.card_head(
            "Language of this conversation",
            "You can switch at any time — just write in the other language and I'll follow.",
        )
        st.radio(
            "Language", ["English", "Deutsch"], horizontal=True,
            label_visibility="collapsed", key="lang_choice",
        )

    left, right = st.columns(2, gap="medium")

    with left:
        with ui.card("cv"):
            ui.card_head("Your CV", "PDF or Word, up to 10 MB.", "Required", "req")
            cv_mode = st.radio(
                "CV input", ["Upload", "Paste text"], horizontal=True,
                label_visibility="collapsed", key="cv_mode",
            )
            cv_file, cv_pasted = None, ""
            if cv_mode == "Upload":
                cv_file = st.file_uploader(
                    "CV", type=["pdf", "docx"], key="cv_upload", label_visibility="collapsed"
                )
            else:
                cv_pasted = st.text_area(
                    "CV text", height=180, key="cv_paste", label_visibility="collapsed",
                    placeholder="Paste the full text of your CV here…",
                )

    with right:
        with ui.card("role"):
            ui.card_head(
                "Target role",
                "With one, the feedback is role-specific. Without one, it covers structure "
                "and completeness — your CV can stand alone.",
                "Optional", "opt",
            )
            jd_mode = st.radio(
                "Job description", ["Skip", "Upload", "Paste text"], horizontal=True,
                label_visibility="collapsed", key="jd_mode",
            )
            jd_file, jd_pasted = None, ""
            if jd_mode == "Upload":
                jd_file = st.file_uploader(
                    "Job description", type=["pdf", "docx"], key="jd_upload",
                    label_visibility="collapsed",
                )
            elif jd_mode == "Paste text":
                jd_pasted = st.text_area(
                    "Job description text", height=180, key="jd_paste",
                    label_visibility="collapsed",
                    placeholder="Paste the job description here…",
                )
            target_hint = st.text_input(
                "Or simply name the role or industry",
                placeholder="e.g. Audit Intern, Sustainability Consulting",
            )

    ready = cv_file is not None or bool(cv_pasted.strip())
    if st.button("Start coaching session", type="primary", disabled=not ready):
        if cv_file is not None:
            cv_result = extract_text(cv_file.getvalue(), cv_file.name)
            if not cv_result.ok:
                st.error(cv_result.error, icon="📄")
                st.stop()
            cv_raw, cv_meta = cv_result.text, cv_result.meta
        else:
            if len(cv_pasted.strip()) < MIN_CHARS:
                st.error(
                    "That's very little text to work with — please paste the full CV.",
                    icon="📄",
                )
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
        with st.spinner("Removing personal details…"):
            cv_clean = strip_pii(cv_raw, cv_language)
            jd_clean = strip_pii(jd_raw, cv_language) if jd_raw.strip() else None

        cv_text = cv_clean["text"]
        st.session_state["cv_text"] = cv_text
        st.session_state["cv_redactions"] = cv_clean["redactions"]
        st.session_state["pii_degraded"] = cv_clean["degraded"]
        st.session_state["date_findings"] = dates.find_findings(cv_text)
        st.session_state["format_rows"] = format_check.run(cv_text, cv_meta)
        if jd_clean:
            st.session_state["jd_text"] = jd_clean["text"]
            st.session_state["jd_redactions"] = jd_clean["redactions"]
        st.session_state["target_role_hint"] = target_role

        # --- only now, on the redacted text, do the two model calls: the section
        # parse and the opening report. They're independent, so they run at once. ---
        lang_code = st.session_state["language_pref"]
        with st.spinner("Reading your CV and writing your feedback report…"):
            with ThreadPoolExecutor(max_workers=2) as pool:
                sections_job = pool.submit(
                    section_coverage.detect_sections, cv_text, client, MODEL
                )
                report_job = pool.submit(
                    report.generate, client, MODEL, cv_text,
                    st.session_state["jd_text"], target_role,
                    st.session_state["format_rows"], language.SUPPORTED[lang_code],
                )
                st.session_state["sections_detected"] = sections_job.result()
                report_data = report_job.result()

        if report_data:
            strings = dict(report.STRINGS[lang_code])
            strings["criteria_note"] = format_check.CRITERIA_NOTE
            report_text = report.render_markdown(
                report_data, st.session_state["format_rows"], strings
            )
            st.session_state["report_text"] = report_text
        else:
            report_text = report.FAILURE_TEXT[lang_code]
        st.session_state["messages"].append({"role": "assistant", "content": report_text})
        st.rerun()

    st.stop()

# --- Step 2: chat -------------------------------------------------------------
ui.title_block(copy["title"], compact=True)
document_panel()

target_role_known = bool(st.session_state["jd_text"] or st.session_state["target_role_hint"])

col_summary, col_report, col_reset = st.columns([3, 2, 2], gap="small")
with col_summary:
    summary_clicked = st.button(
        "Prepare a summary for Career Services",
        disabled=len(st.session_state["messages"]) < 3,
        help="Available at any time — you don't have to wait for the bot to offer one.",
        use_container_width=True,
    )
with col_report:
    if st.session_state["report_text"]:
        st.download_button(
            "Download the report",
            data=st.session_state["report_text"],
            file_name="cv_feedback_report.md",
            mime="text/markdown",
            help="The feedback report from the start of this conversation. Markdown, "
                 "so the tables keep their shape.",
            use_container_width=True,
            key="report_download",
        )
with col_reset:
    if st.button("Start over", use_container_width=True):
        reset_session()
        st.rerun()

if summary_clicked:
    summary_messages = prompts.build_summary_messages(
        st.session_state["messages"], st.session_state["sections_detected"],
        lang, language.SUPPORTED[lang],
    )
    with st.spinner("Preparing summary…"):
        manual_summary_text = latency.stream_response(
            client, MODEL, summary_messages, lambda _: None,
            max_tokens=latency.SUMMARY_MAX_TOKENS, timeout=latency.SUMMARY_TIMEOUT_SECONDS,
        )
    with ui.card("summary"):
        st.markdown(manual_summary_text)
        st.download_button(
            "Download summary (.txt)",
            data=manual_summary_text, file_name="cv_coach_summary.txt", mime="text/plain",
            key="manual_summary_download",
        )

# A CV with nothing under involvement gets shown what HSG actually offers.
# Static content from hsg_activities.GIST - the same source the conversation
# uses, so the panel and the bot can never contradict each other.
if hsg_activities.looks_thin(
    section_coverage.categories(st.session_state["sections_detected"])
):
    with ui.card("hsg"):
        ui.card_head(
            "Where HSG students build this kind of experience",
            "Things HSG offers that students often forget to put on a CV, and which "
            "section each one belongs in. Ask me about any of them — or about anything "
            "you've already done that isn't listed here.",
        )
        ui.gist_rows(hsg_activities.GIST)

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if st.session_state["handed_over"]:
    st.info("This session has been flagged for a human advisor. Coaching is paused here.")
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
        st.session_state["date_findings"],
        st.session_state["sections_detected"],
    )
    api_messages = [{"role": "system", "content": prompts.SYSTEM_PROMPT}]
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
