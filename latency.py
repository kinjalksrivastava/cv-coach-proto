"""
Latency handling for the <6s-per-turn budget.

A hard, guaranteed 6-second cap on a third-party model's total
generation time isn't something a client can enforce without risking
truncated answers - that's an honest limit, not an oversight (see
README). What IS controllable from here:

  - Streaming, so the student sees the first tokens almost immediately
    instead of waiting for the full response - this is what makes the
    turn FEEL fast, and is the main lever for the 6s target in practice.
  - A request timeout, so a stalled call fails fast with a clear
    message instead of hanging indefinitely.
  - A response length cap. This one's a genuine trade-off, not a free
    latency win: too low and the model gets visibly cut off mid-answer
    (this happened - the original 350-token default didn't leave room
    for a proactive section transition plus a new question in one
    turn). CHAT_MAX_TOKENS is set with headroom for that. The summary
    is a different shape of output entirely - a multi-section document,
    not a chat turn - so it gets its own, larger cap rather than
    sharing the chat one.
"""

import json
from collections.abc import Callable

REQUEST_TIMEOUT_SECONDS = 12          # hard safety net for a stalled/slow chat turn
SUMMARY_TIMEOUT_SECONDS = 25          # summaries are intentionally longer generations

CHAT_MAX_TOKENS = 600                 # normal coaching turns
SUMMARY_MAX_TOKENS = 1200             # end-of-conversation summary (multi-section)

FALLBACK_MESSAGE = (
    "That's taking longer than expected. Please try sending your message again."
)


def stream_response(
    client,
    model: str,
    messages: list[dict],
    on_delta: Callable[[str], None],
    max_tokens: int = CHAT_MAX_TOKENS,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
) -> str:
    """
    Streams a chat completion. Calls on_delta(full_text_so_far) as each
    chunk arrives so the caller (e.g. a Streamlit placeholder) can render
    incrementally. Returns the final full text, or FALLBACK_MESSAGE on
    a timeout/API error - the caller should treat that return value as
    the whole answer for this turn either way.

    Pass max_tokens/timeout explicitly for anything that isn't a normal
    chat turn (see SUMMARY_MAX_TOKENS / SUMMARY_TIMEOUT_SECONDS above) -
    don't silently reuse the chat defaults for a differently-shaped call.
    """
    collected = ""
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                collected += delta
                on_delta(collected)
    except Exception:
        return FALLBACK_MESSAGE

    return collected or FALLBACK_MESSAGE


# --- Non-streaming JSON calls (document analysis at intake) -------------------
#
# PII detection and CV-section parsing are one-off calls made while the student
# waits on the upload screen, not chat turns - so they don't share the <6s
# per-turn budget, and they want a parsed object rather than streamed prose.
# They run concurrently in app.py, so the wall-clock cost of both is one call.

ANALYSIS_TIMEOUT_SECONDS = 30
ANALYSIS_MAX_TOKENS = 2000


def json_call(
    client,
    model: str,
    messages: list[dict],
    max_tokens: int = ANALYSIS_MAX_TOKENS,
    timeout: int = ANALYSIS_TIMEOUT_SECONDS,
) -> dict | None:
    """
    One non-streaming call constrained to a JSON object response. Returns the
    parsed dict, or None on any failure (timeout, API error, malformed JSON) -
    every caller must have a working non-LLM fallback for that None, since a
    document analysis failing should degrade the app, never break it.
    """
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout,
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(completion.choices[0].message.content)
    except Exception:
        return None
