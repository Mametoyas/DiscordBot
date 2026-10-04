"""Phase 1: PLAN — port of discord-bot-agents/src/agent/planner.js."""

import logging

from src.core import llm
from .language import detect_language, language_instruction
from .prompts import build_planning_prompt

log = logging.getLogger("gemini-bot")


async def plan(user_text: str, message, prefetch: dict | None = None) -> dict:
    from src import config

    prefetch = prefetch or {}
    detected = detect_language(user_text)
    prompt = build_planning_prompt(message, user_text, prefetch)
    prompt += f"\n\n{language_instruction(detected, 'plan')}\nReturn JSON only: {{\"reasoning\":\"...\",\"actions\":[...]}} — no reply field. If genuinely torn between 2-4 concrete options that change the outcome, you may ALSO add \"question\":\"...\" and \"options\":[\"...\"...] (user picks a button or types their own); otherwise infer defaults and omit them."
    raw = await llm.generate_text(prompt, temperature=0.0)
    parsed = llm.extract_json(raw)
    if not parsed or not isinstance(parsed, dict):
        log.warning("[Agent/Plan] JSON parse failed. Preview: %s", raw[:400])
        return {"reasoning": "Parse failure", "actions": []}

    actions = parsed.get("actions") if isinstance(parsed.get("actions"), list) else []
    actions = [
        {"skill": a["skill"], "params": a["params"] if isinstance(a.get("params"), dict) else {}}
        for a in actions
        if isinstance(a, dict) and isinstance(a.get("skill"), str)
    ][: config.MAX_ACTIONS]

    seen, deduped = set(), []
    for a in actions:
        key = a["skill"] + ":" + str(sorted(a["params"].items()))
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    # Fallback: pasted layout the LLM couldn't turn into JSON — parse it directly.
    # (e.g. "[Category: X] Text Channels: a, b / Voice Channels: c" blocks)
    has_layout_action = any(
        a["skill"] == "restructureServer" and a["params"].get("layout")
        for a in deduped
    )
    if not has_layout_action:
        try:
            from src.skills.channels import extract_layout

            layout = extract_layout(user_text)
        except Exception:
            layout = []
        if layout:
            deduped.insert(0, {"skill": "restructureServer", "params": {"layout": layout}})
            log.info("[Agent/Plan] layout extracted from message: %d categories", len(layout))

    options = parsed.get("options") if isinstance(parsed.get("options"), list) else []
    options = [str(o)[:80] for o in options if o][:4]
    question = parsed.get("question") if isinstance(parsed.get("question"), str) else None
    if not (question and options):
        question, options = None, []

    return {"reasoning": parsed.get("reasoning", ""), "actions": deduped,
            "question": question, "options": options}
