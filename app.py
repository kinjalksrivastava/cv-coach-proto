import os

import streamlit as st
from openai import OpenAI

from extraction import extract_text, MIN_CHARS
from pii import strip_pii
from guardrails import confidentiality, global_rules, language, dates, section_coverage
from sections import jd_alignment
import prompts
import latency

MODEL = "gpt-4.1"

st.set_page_config(page_title="HSG CV Coach (prototype)", page_icon="📄", layout="centered")


def _configured_key() -> str | None:
    """
    The shared key you configure once, so anyone with the app's link can use it
    with zero setup on their end. Checked in this order:
      1. Streamlit secrets (.streamlit/secrets.toml locally, or the "Secrets" box
         in Streamlit Community Cloud's app settings when deployed)
      2. OPENAI_API_KEY environment variable
    Wrapped in try/except because st.secrets raises if no secrets.toml exists at
    all (e.g. a fresh local checkout before you've created one) - that should
    fall through quietly, not crash the app.
    """
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY")


def get_client() -> OpenAI | None:
    # A key typed into the sidebar (e.g. by a tester using their own quota)
    # always wins over the shared configured one, but isn't required.
    api_key = st.session_state.get("api_key") or _configured_key()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def init_state():
    defaults = {
        "cv_text": None,
        "cv_redactions": [],
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
        "api_key": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_session():
    for k in list(st.session_state.keys()):
        if k != "api_key":
            del st.session_state[k]
    init_state()


init_state()

with st.sidebar:
    st.markdown("### Prototype settings")
    if _configured_key():
        st.success("Using the shared API key — no setup needed.", icon="✅")
    st.session_state["api_key"] = st.text_input(
        "Use a different API key instead (optional)",
        value=st.session_state["api_key"],
        type="password",
        help="Only needed to override the shared key above — e.g. to test against your own quota.",
    )
    st.caption(f"Model: {MODEL}")
    if st.button("Reset session", use_container_width=True):
        reset_session()
        st.rerun()
    st.divider()
    st.warning(
        "**Prototype, not production.** No Swiss hosting, no signed DPA with OpenAI "
        "yet, PII stripping and date-gap detection are both regex-based (best-effort, "
        "not certified). Use dummy CVs, not real student documents.",
        icon="⚠️",
    )

st.title("📄 HSG CV Coach — prototype")
st.caption(
    "Session data lives only in this browser tab's memory and clears on reset — "
    "no permanent storage in this prototype."
)

client = get_client()
if client is None:
    st.info("No API key configured yet. Enter one in the sidebar to start, or "
             "set OPENAI_API_KEY / Streamlit secrets — see README.md.")
    st.stop()

# --- Step 1: document intake -------------------------------------------------
if st.session_state["cv_text"] is None:
    st.subheader("1. Session language")
    lang_choice = st.radio("Ask upfront — you can still switch mid-conversation.",
                            ["English", "Deutsch"], horizontal=True)
    st.session_state["language_pref"] = "en" if lang_choice == "English" else "de"
    st.session_state["effective_language"] = st.session_state["language_pref"]

    st.subheader("2. CV — required")
    cv_mode = st.radio("CV input", ["Upload file (PDF/DOCX)", "Paste text"], horizontal=True, key="cv_mode")
    cv_file, cv_pasted = None, ""
    if cv_mode == "Upload file (PDF/DOCX)":
        cv_file = st.file_uploader("CV", type=["pdf", "docx"], key="cv_upload")
    else:
        cv_pasted = st.text_area("Paste CV text", height=200, key="cv_paste")

    st.subheader("3. Target role — optional, CV can stand alone without one")
    jd_mode = st.radio(
        "Job description", ["Skip — I don't have one", "Upload file (PDF/DOCX)", "Paste text"],
        horizontal=True, key="jd_mode",
    )
    jd_file, jd_pasted, target_hint = None, "", ""
    if jd_mode == "Upload file (PDF/DOCX)":
        jd_file = st.file_uploader("Job description", type=["pdf", "docx"], key="jd_upload")
    elif jd_mode == "Paste text":
        jd_pasted = st.text_area("Paste job description text", height=150, key="jd_paste")
    target_hint = st.text_input("...or just name the target role/industry (optional)")

    ready = cv_file is not None or bool(cv_pasted.strip())
    if st.button("Start coaching session", type="primary", disabled=not ready):
        if cv_file is not None:
            cv_result = extract_text(cv_file.getvalue(), cv_file.name)
            if not cv_result.ok:
                st.error(cv_result.error)
                st.stop()
            cv_raw = cv_result.text
        else:
            if len(cv_pasted.strip()) < MIN_CHARS:
                st.error("That's very little text to work with — please paste the full CV.")
                st.stop()
            cv_raw = cv_pasted

        cv_clean = strip_pii(cv_raw)
        st.session_state["cv_text"] = cv_clean["text"]
        st.session_state["cv_redactions"] = cv_clean["redactions"]
        st.session_state["date_findings"] = dates.find_findings(cv_raw)
        st.session_state["sections_detected"] = section_coverage.detect_sections(cv_clean["text"])

        if jd_file is not None:
            jd_result = extract_text(jd_file.getvalue(), jd_file.name)
            if jd_result.ok:
                jd_clean = strip_pii(jd_result.text)
                st.session_state["jd_text"] = jd_clean["text"]
                st.session_state["jd_redactions"] = jd_clean["redactions"]
            else:
                st.warning(f"Job description could not be used: {jd_result.error}")
        elif jd_pasted.strip():
            jd_clean = strip_pii(jd_pasted)
            st.session_state["jd_text"] = jd_clean["text"]
            st.session_state["jd_redactions"] = jd_clean["redactions"]

        st.session_state["target_role_hint"] = target_hint.strip()

        intro = "I've processed your CV." if st.session_state["language_pref"] == "en" \
            else "Ich habe deinen Lebenslauf verarbeitet."
        if st.session_state["cv_redactions"]:
            intro += f" (Redacted: {', '.join(st.session_state['cv_redactions'])}.)"
        st.session_state["messages"].append({"role": "assistant", "content": intro})
        st.rerun()

    st.stop()

# --- Step 2: chat -------------------------------------------------------------
target_role_known = bool(st.session_state["jd_text"] or st.session_state["target_role_hint"])

with st.expander("Session info", expanded=False):
    st.write("Effective language:", language.SUPPORTED[st.session_state["effective_language"]])
    st.write("CV redactions applied:", st.session_state["cv_redactions"] or "none detected")
    if st.session_state["jd_text"]:
        st.write("Job description redactions:", st.session_state["jd_redactions"] or "none detected")
    if st.session_state["target_role_hint"]:
        st.write("Target role hint:", st.session_state["target_role_hint"])
    st.write("Target role established:", target_role_known)
    st.write("Structure-only mode:", st.session_state["structure_only_mode"])
    st.write("Sections detected:", st.session_state["sections_detected"] or "none detected")
    if st.session_state["date_findings"]:
        st.write("Date flags:", st.session_state["date_findings"])

if st.button("📋 Prepare a summary now (for Career Services)",
             disabled=len(st.session_state["messages"]) < 2,
             help="Available any time - you don't have to wait for the bot to offer one."):
    manual_lang_code = st.session_state["effective_language"]
    manual_lang_name = language.SUPPORTED[manual_lang_code]
    summary_messages = prompts.build_summary_messages(
        st.session_state["messages"], st.session_state["sections_detected"], manual_lang_code, manual_lang_name
    )
    with st.spinner("Preparing summary..."):
        manual_summary_text = latency.stream_response(
            client, MODEL, summary_messages, lambda _: None,
            max_tokens=latency.SUMMARY_MAX_TOKENS, timeout=latency.SUMMARY_TIMEOUT_SECONDS,
        )
    st.markdown(manual_summary_text)
    st.download_button(
        "⬇️ Download summary (.txt) to email Career Services",
        data=manual_summary_text, file_name="cv_coach_summary.txt", mime="text/plain",
        key="manual_summary_download",
    )

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if st.session_state["handed_over"]:
    st.info("This session has been flagged for a human advisor. Coaching is paused here.")
    st.stop()

user_input = st.chat_input("Ask about your CV...")

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
                st.session_state["messages"], st.session_state["sections_detected"], lang_code, lang_name
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
                    "⬇️ Download summary (.txt) to email Career Services",
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
            {"role": "system", "content": f"Student-stated target role/industry: {st.session_state['target_role_hint']}"}
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
