"""Phase 3: SUMMARIZE — natural reply from real results."""

from src.core import llm
from .language import detect_language, language_instruction
from .prompts import build_summarize_prompt


async def summarize(user_text: str, message, prefetch: dict, plan: dict, results: list) -> dict:
    prompt = build_summarize_prompt(message, user_text, prefetch or {}, plan, results)
    prompt += f"\n\n{language_instruction(detect_language(user_text), 'summarize')}"
    raw = await llm.generate_text(prompt, temperature=0.7)
    parsed = llm.extract_json(raw) or {}
    reply = parsed.get("reply") if isinstance(parsed.get("reply"), str) else None
    if not reply:
        ok = [r for r in results if r.get("status") == "success"]
        bad = [r for r in results if r.get("status") == "failed"]
        if results and not bad:
            reply = f"Done — {len(ok)} action(s) completed."
        elif bad:
            reply = "I couldn't complete that: " + "; ".join(
                r.get("error", "?") for r in bad[:3]
            )
        else:
            reply = "I am not sure what you meant. Please rephrase your server-management request."
    return {"reply": reply[:1900], "replyFormat": parsed.get("replyFormat", "text")}
