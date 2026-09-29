"""Agent entry point — mirrors discord-bot-agents/src/agent/index.js.

Plan → Execute → Summarize. Cost profile:
  - Empty @Bot mention: 0 LLM (handled in handler)
  - Normal command: 2 LLM calls (plan + summarize)
"""

import logging

from . import planner, executor, summarizer
from .composer import compose
from .prefetch import prefetch_query_data

log = logging.getLogger("gemini-bot")


async def run(user_text: str, message) -> dict:
    prefetched = await prefetch_query_data(user_text, message)

    log.info("[Agent] Planning: %s", user_text[:100])
    decision = await planner.plan(user_text, message, prefetched)
    log.info("[Agent] Actions=%d | %s", len(decision["actions"]), decision.get("reasoning", "")[:140])

    results = await executor.execute(decision["actions"], message)

    log.info("[Agent] Summarizing (%d result(s))...", len(results))
    summary = await summarizer.summarize(user_text, message, prefetched, decision, results)
    output = compose(summary, results)

    return {**output, "plan": decision, "results": results}
