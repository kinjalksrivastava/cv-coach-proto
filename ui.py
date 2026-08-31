"""
Presentation layer: the stylesheet, the University of St.Gallen header, and the
small reusable pieces (cards, chips, section labels) the app renders.

Kept out of app.py deliberately, for the same reason the coaching rules live in
prompts.py / guardrails/ / sections/ — app.py stays orchestration only. Nothing
in here knows anything about CV rules; nothing outside here writes CSS.

The logo files in assets/ are the university's own SVGs (mark + wordmark), taken
from unisg.ch, English and German variants. #00802F is HSG's corporate green,
from the same source.
"""

from functools import lru_cache
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"

GREEN = "#00802F"
GREEN_DARK = "#00632A"

STYLES = f"""
<style>
:root {{
  --hsg-green: {GREEN};
  --hsg-green-dark: {GREEN_DARK};
  --hsg-green-tint: #EAF3ED;
  --ink: #15181A;
  --ink-soft: #55605A;
  --ink-faint: #7C8781;
  --border: #E1E7E3;
  --surface: #FFFFFF;
  --canvas: #F7F9F8;
}}

/* --- shell ------------------------------------------------------------- */
html, body, [class*="st-"], button, input, textarea, select {{
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI",
               "Helvetica Neue", Arial, sans-serif;
}}
[data-testid="stAppViewContainer"] {{ background: var(--canvas); }}
[data-testid="stHeader"] {{ background: transparent; height: 0; }}
[data-testid="stToolbar"] {{ display: none; }}
[data-testid="stDecoration"] {{ display: none; }}
footer {{ display: none; }}
#MainMenu {{ display: none; }}
[data-testid="stMainBlockContainer"], .block-container {{
  max-width: 980px;
  padding-top: 2.2rem;
  padding-bottom: 4rem;
}}

/* --- masthead ---------------------------------------------------------- */
.hsg-masthead {{
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 1.5rem; padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}}
.hsg-masthead svg {{ height: 38px; width: auto; display: block; }}
.hsg-unit {{
  font-size: 0.78rem; letter-spacing: 0.09em; text-transform: uppercase;
  color: var(--ink-faint); font-weight: 600; padding-bottom: 3px;
}}
.hsg-title-block {{ padding: 1.6rem 0 1.9rem 0; }}
.hsg-title-block h1 {{
  font-size: 2.15rem; font-weight: 680; letter-spacing: -0.02em;
  color: var(--ink); margin: 0 0 0.35rem 0; padding: 0; line-height: 1.15;
}}
.hsg-title-block.compact {{ padding: 1.1rem 0 1.1rem 0; }}
.hsg-title-block.compact h1 {{ font-size: 1.6rem; margin-bottom: 0; }}
.hsg-title-block p {{
  font-size: 1rem; color: var(--ink-soft); margin: 0; max-width: 62ch;
  line-height: 1.55;
}}

/* --- cards ------------------------------------------------------------- */
.hsg-card {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; padding: 1.5rem 1.6rem; margin-bottom: 1.1rem;
}}
.hsg-card-head {{
  display: flex; align-items: baseline; gap: 0.6rem; margin-bottom: 0.15rem;
}}
.hsg-card-head .t {{ font-size: 1rem; font-weight: 640; color: var(--ink); }}
.hsg-card-head .badge {{
  font-size: 0.68rem; letter-spacing: 0.07em; text-transform: uppercase;
  font-weight: 650; padding: 2px 8px; border-radius: 999px;
}}
.badge-req {{ background: var(--hsg-green-tint); color: var(--hsg-green-dark); }}
.badge-opt {{ background: #F1F3F2; color: var(--ink-faint); }}
.hsg-card-sub {{
  font-size: 0.87rem; color: var(--ink-soft); margin: 0 0 0.9rem 0;
  line-height: 1.5;
}}
.hsg-rule {{ height: 1px; background: var(--border); margin: 0.2rem 0 1.2rem 0; }}

/* --- cards: drawn here, not by Streamlit's own border ------------------- */
[class*="st-key-hsgcard_"] {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.35rem 1.5rem 1.45rem 1.5rem;
  height: 100%;
}}
[data-testid="stHorizontalBlock"] {{ align-items: stretch; }}
[data-testid="stColumn"] {{ display: flex; }}
[data-testid="stColumn"] > div,
[data-testid="stColumn"] [data-testid="stVerticalBlock"] {{ height: 100%; flex: 1; }}
[class*="st-key-hsgcard_"] [data-testid="stVerticalBlock"] {{ gap: 0.75rem; }}

/* --- chips ------------------------------------------------------------- */
.hsg-chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 2px; }}
.hsg-chip {{
  font-size: 0.8rem; padding: 4px 11px; border-radius: 999px;
  border: 1px solid var(--border); background: #fff; color: var(--ink-soft);
  white-space: nowrap;
}}
.hsg-chip.on {{
  border-color: #BFDFCB; background: var(--hsg-green-tint);
  color: var(--hsg-green-dark); font-weight: 550;
}}
.hsg-chip.muted {{ color: var(--ink-faint); background: #FAFBFA; }}
.hsg-panel-label {{
  font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase;
  font-weight: 650; color: var(--ink-faint); margin: 0 0 6px 0;
}}
.hsg-panel-row {{ margin-top: 1.05rem; }}
.hsg-note {{
  font-size: 0.85rem; color: var(--ink-soft); line-height: 1.5; margin: 3px 0 0 0;
}}
.hsg-note.q {{
  border-left: 2px solid #DCE4DF; padding-left: 10px; margin-top: 6px;
}}

/* --- radios as segmented pills ----------------------------------------- */
[data-testid="stRadio"] > label {{
  font-size: 0.87rem !important; color: var(--ink-soft) !important;
  font-weight: 500 !important;
}}
div[role="radiogroup"] {{ gap: 8px !important; }}
div[role="radiogroup"] > label {{
  border: 1px solid var(--border); border-radius: 999px;
  padding: 5px 15px 5px 13px; background: #fff; margin: 0 !important;
  transition: border-color .12s ease, background .12s ease;
}}
div[role="radiogroup"] > label:hover {{ border-color: #C4D4CA; }}
div[role="radiogroup"] > label:has(input:checked) {{
  border-color: var(--hsg-green); background: var(--hsg-green-tint);
}}
div[role="radiogroup"] > label > div:first-child {{ display: none !important; }}
div[role="radiogroup"] > label p {{
  font-size: 0.87rem !important; color: var(--ink) !important; font-weight: 500;
}}

/* --- uploader: a calm card, not a dashed drop target -------------------- */
[data-testid="stFileUploaderDropzone"] {{
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  background: #FBFCFB !important;
  padding: 0.85rem 1rem !important;
  min-height: 0 !important;
}}
[data-testid="stFileUploaderDropzone"]:hover {{ border-color: #C4D4CA !important; }}
[data-testid="stFileUploaderDropzone"] [data-testid="stIconMaterial"] {{ display: none; }}
[data-testid="stFileUploaderDropzoneInstructions"] span {{
  color: var(--ink-faint) !important; font-size: 0.78rem !important;
}}
[data-testid="stFileUploaderDropzone"] button {{
  border-radius: 8px !important; border: 1px solid var(--border) !important;
  color: var(--ink) !important; font-weight: 550 !important;
}}
[data-testid="stFileUploaderFile"] {{ font-size: 0.85rem; }}

/* --- inputs ------------------------------------------------------------ */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
[data-testid="stTextInputRootElement"], [data-baseweb="textarea"] {{
  border-radius: 10px !important; border-color: var(--border) !important;
  background: #FFFFFF !important; font-size: 0.9rem !important;
}}
[data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus {{
  border-color: var(--hsg-green) !important; box-shadow: none !important;
}}
[data-testid="stWidgetLabel"] p {{
  font-size: 0.87rem !important; color: var(--ink-soft) !important;
}}

/* --- buttons ----------------------------------------------------------- */
button[kind="primary"], [data-testid="stBaseButton-primary"] {{
  background: var(--hsg-green) !important; border: 1px solid var(--hsg-green) !important;
  border-radius: 10px !important; font-weight: 600 !important;
  padding: 0.55rem 1.1rem !important;
}}
button[kind="primary"]:disabled, [data-testid="stBaseButton-primary"]:disabled {{
  background: #EDF1EE !important; border-color: var(--border) !important;
  color: var(--ink-faint) !important;
}}
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {{
  background: var(--hsg-green-dark) !important; border-color: var(--hsg-green-dark) !important;
}}
button[kind="secondary"], [data-testid="stBaseButton-secondary"] {{
  border-radius: 10px !important; border: 1px solid var(--border) !important;
  color: var(--ink) !important; background: #fff !important; font-weight: 550 !important;
}}
button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover {{
  border-color: var(--hsg-green) !important; color: var(--hsg-green-dark) !important;
}}
[data-testid="stDownloadButton"] button {{
  border-radius: 10px !important; border: 1px solid #BFDFCB !important;
  background: var(--hsg-green-tint) !important; color: var(--hsg-green-dark) !important;
  font-weight: 600 !important;
}}

/* --- chat -------------------------------------------------------------- */
/* No avatars: the tinted background already separates the two speakers, and a
   generic bot glyph adds nothing to a Career Services page. */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {{ display: none !important; }}
[data-testid="stChatMessage"] {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem;
}}
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {{
  font-size: 0.94rem; line-height: 1.62;
}}
/* The opening feedback report is a document inside a chat bubble: scale its
   headings down so it reads as one, and drop Streamlit's heading anchor links. */
[data-testid="stChatMessage"] h2 {{
  font-size: 1.28rem; font-weight: 660; padding: 0 0 0.2rem 0; letter-spacing: -0.01em;
}}
[data-testid="stChatMessage"] h3 {{
  font-size: 1.02rem; font-weight: 640; padding: 1.1rem 0 0.1rem 0;
  color: var(--hsg-green-dark);
}}
[data-testid="stChatMessage"] [data-testid="stHeaderActionElements"] {{ display: none; }}
[data-testid="stChatMessage"] table {{ font-size: 0.86rem; }}
[data-testid="stChatMessage"] th {{
  background: #F6F8F7; font-weight: 620; text-align: left;
}}
[data-testid="stChatMessage"] td, [data-testid="stChatMessage"] th {{
  border-color: var(--border) !important; padding: 7px 10px !important;
}}
[data-testid="stChatMessage"] hr {{ margin: 1.4rem 0 1rem 0; }}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
  background: var(--hsg-green-tint); border-color: #DCEBE1;
}}
[data-testid="stChatInput"] {{
  background: #FFFFFF !important; border: 1px solid var(--border) !important;
  border-radius: 12px !important;
}}
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] textarea,
[data-testid="stChatInputTextArea"] {{ background: #FFFFFF !important; }}
[data-testid="stBottom"], [data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] {{ background: var(--canvas) !important; }}
[data-testid="stBottomBlockContainer"] {{ max-width: 980px; padding-bottom: 1.1rem; }}

/* --- misc -------------------------------------------------------------- */
[data-testid="stAlert"] {{ border-radius: 12px; }}
hr {{ border-color: var(--border); }}
</style>
"""


@lru_cache(maxsize=4)
def _logo_svg(language_code: str) -> str:
    """The university's own wordmark, EN or DE. Cached — it's read from disk."""
    name = "hsg_logo_de.svg" if language_code == "de" else "hsg_logo_en.svg"
    path = ASSETS / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        # Never let a missing asset break the app — fall back to plain text.
        return '<span style="font-weight:650;color:#00802F">University of St.Gallen</span>'


def page_icon() -> str:
    path = ASSETS / "hsg_favicon.png"
    return str(path) if path.exists() else "📄"


def inject_styles() -> None:
    st.markdown(STYLES, unsafe_allow_html=True)


def masthead(language_code: str = "en", unit_label: str = "Career Services") -> None:
    st.markdown(
        f'<div class="hsg-masthead">{_logo_svg(language_code)}'
        f'<div class="hsg-unit">{unit_label}</div></div>',
        unsafe_allow_html=True,
    )


def title_block(title: str, subtitle: str = "", compact: bool = False) -> None:
    """Full lockup on the intake screen; compact once the conversation is running."""
    cls = "hsg-title-block compact" if compact else "hsg-title-block"
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="{cls}"><h1>{title}</h1>{sub}</div>', unsafe_allow_html=True)


def card(key: str):
    """
    A bordered white panel. Streamlit's own border=True is not used - the card is
    drawn from CSS keyed on the container's key, which survives Streamlit's
    generated class names changing between versions.
    """
    return st.container(key=f"hsgcard_{key}")


def card_head(title: str, subtitle: str = "", badge: str = "", badge_kind: str = "req") -> None:
    """Header for a bordered section. Rendered above the widgets it introduces."""
    badge_html = f'<span class="badge badge-{badge_kind}">{badge}</span>' if badge else ""
    sub_html = f'<p class="hsg-card-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="hsg-card-head"><span class="t">{title}</span>{badge_html}</div>'
        f"{sub_html}",
        unsafe_allow_html=True,
    )


def rule() -> None:
    st.markdown('<div class="hsg-rule"></div>', unsafe_allow_html=True)


def chips(label: str, items: list[str], kind: str = "on", empty_text: str = "none") -> None:
    """A labelled row of pills — what was detected, what was removed, and so on."""
    if items:
        body = "".join(f'<span class="hsg-chip {kind}">{i}</span>' for i in items)
    else:
        body = f'<span class="hsg-chip muted">{empty_text}</span>'
    st.markdown(
        f'<div class="hsg-panel-row"><p class="hsg-panel-label">{label}</p>'
        f'<div class="hsg-chips">{body}</div></div>',
        unsafe_allow_html=True,
    )


def notes(label: str, lines: list[str]) -> None:
    body = "".join(f'<p class="hsg-note q">{line}</p>' for line in lines)
    st.markdown(
        f'<div class="hsg-panel-row"><p class="hsg-panel-label">{label}</p>{body}</div>',
        unsafe_allow_html=True,
    )
