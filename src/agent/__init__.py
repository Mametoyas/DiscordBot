"""Agent entry point — mirrors discord-bot-agents/src/agent/index.js.

Plan → Execute → Summarize. Cost profile:
  - Empty @Bot mention: 0 LLM (handled in handler)
  - Chit-chat / no-action plan: 1 LLM call (planner only, handler falls back to chat)
  - Normal command: 2 LLM calls (plan + summarize)
  - No actions planned -> returns reply=None so the caller can chat instead.
"""

import logging

from . import planner, executor, summarizer
from .composer import compose
from .prefetch import prefetch_query_data

log = logging.getLogger("gemini-bot")


async def run(user_text: str, message, confirm_fn=None) -> dict:
    """confirm_fn(actions) -> bool: asked BEFORE anything executes.
    None (or no actions) means chat-fallback territory as before."""
    prefetched = await prefetch_query_data(user_text, message)

    log.info("[Agent] Planning: %s", user_text[:100])
    decision = await planner.plan(user_text, message, prefetched)
    log.info("[Agent] Actions=%d | %s", len(decision["actions"]), decision.get("reasoning", "")[:140])

    if not decision["actions"]:
        # Nothing to execute (chit-chat, question, or out-of-scope) — let the
        # caller fall back to free chat instead of a stiff refusal. reply=None
        # signals this; skipping summarize saves one LLM call.
        return {"reply": None, "plan": decision, "results": []}

    pre_confirmed = False
    if confirm_fn is not None:
        try:
            pre_confirmed = bool(await confirm_fn(decision["actions"]))
        except Exception:  # noqa: BLE001 — broken prompt = stay safe
            log.exception("[Agent] confirm_fn failed")
            pre_confirmed = False
        if not pre_confirmed:
            return {"reply": "❌ ยกเลิกแล้ว ไม่ได้ทำอะไร",
                    "plan": decision, "results": [], "cancelled": True}

    results = await executor.execute(decision["actions"], message, pre_confirmed=pre_confirmed)

    log.info("[Agent] Summarizing (%d result(s))...", len(results))
    summary = await summarizer.summarize(user_text, message, prefetched, decision, results)
    output = compose(summary, results)

    return {**output, "plan": decision, "results": results}
