"""Light prefetch for info queries — mirrors agent/prefetch.js.

Discord API only (no LLM cost). Triggers call skill.fetch_raw() where the
skill defines one; param-dependent lookups are left to the planner.
"""

import logging
import re

from src.skills import SKILLS

log = logging.getLogger("gemini-bot")

QUERY_TRIGGERS = {
    "getServerInfo": [r"server info", r"info server", r"server owner", r"เจ้าของเซิร์ฟ|เจ้าของเซิฟ",
                      r"how many members", r"member berapa", r"สมาชิกกี่", r"server id", r"about server"],
    "listChannels": [r"list channel", r"channel list", r"all channels", r"show channel", r"ช่องทั้งหมด|ลิสต์ช่อง"],
    "listRoles": [r"list role", r"role list", r"all roles", r"show role", r"ยศทั้งหมด|โรลทั้งหมด"],
    "listEmojis": [r"list emoji", r"all emojis?", r"show emoji", r"อิโมจิทั้งหมด"],
    "listInvites": [r"list invite", r"all invites", r"ลิงก์เชิญ"],
}

# Questions/teachings that may match shared guild memories
MEMORY_TRIGGERS = [r"จำ|จดไว้|ลืม|ใคร|อะไร|ชื่อ|คือ|remember|forget|who|what|fact"]


async def prefetch_query_data(user_text: str, message) -> dict:
    prefetched: dict = {}
    low = user_text.lower()
    for skill_name, triggers in QUERY_TRIGGERS.items():
        if not any(re.search(t, low) for t in triggers):
            continue
        skill = SKILLS.get(skill_name)
        fetch = getattr(skill, "fetch_raw", None)
        if not fetch:
            continue
        try:
            prefetched[skill_name] = await fetch(message.guild, message)
        except Exception as e:  # noqa: BLE001 — prefetch must never break the run
            log.warning("[Pre-fetch] %s: %s", skill_name, e)
    if message.guild and any(re.search(t, low) for t in MEMORY_TRIGGERS):
        try:
            from src.utils.chat_store import store as _chat_store

            hits = await _chat_store.recall_matching(message.guild.id, user_text, limit=5)
            if hits:
                prefetched["memories"] = [
                    f"[{h.get('category', 'general')}] {h['key']}: {h['content']}" for h in hits
                ]
        except Exception as e:  # noqa: BLE001
            log.warning("[Pre-fetch] memories: %s", e)
    return prefetched
