"""Shared guild memory skills (3): remember/recall/forget.

Ported from discord-agent's Memory tools, backed by Supabase `memories`
(SQL in chat_store.MEMORIES_SETUP) with local fallback. Unlike per-user
chat history, these facts are visible to EVERYONE in the server.
"""

from . import Skill, register
from src.utils.chat_store import store


async def _remember(guild, params, message):
    await store.remember_fact(
        guild.id,
        params.get("key", ""),
        params.get("content", ""),
        params.get("category") or "general",
        message.author.id,
    )
    return f"จำไว้แล้ว: **{params.get('key').strip()}**"


register(Skill(
    name="rememberFact",
    description="Saves a shared fact everyone in the server can recall later (nickname-for-member goes to setMemberAlias instead).",
    params={
        "key": "string - Short title of the fact.",
        "content": "string - The fact itself.",
        "category": "string (optional) - grouping label, default 'general'.",
    },
    execute=_remember,
    required_permissions=["manage_messages"],
))


async def _recall(guild, params, message):
    rows = await store.recall_matching(guild.id, params.get("query") or "", limit=5)
    if params.get("category"):
        rows = [r for r in rows if r.get("category") == params["category"]]
    if not rows:
        return "ยังไม่มีความจำที่ตรงกันเลย"
    return "\n".join(f"- [{r.get('category', 'general')}] **{r['key']}**: {r['content']}" for r in rows)


register(Skill(
    name="recallFacts",
    description="Searches shared facts remembered for this server.",
    params={
        "query": "string (optional) - keywords to search; empty = recent facts.",
        "category": "string (optional) - filter by category.",
    },
    execute=_recall,
))


async def _forget(guild, params, message):
    ok = await store.forget_fact(guild.id, params.get("key", ""), params.get("category") or "general")
    if not ok:
        raise ValueError(f"ไม่มีความจำหัวข้อ \"{params.get('key')}\"")
    return f"ลืมเรื่อง **{params.get('key').strip()}** แล้ว"


register(Skill(
    name="forgetFact",
    description="Deletes one shared fact from this server's memory.",
    params={
        "key": "string - The fact title to forget.",
        "category": "string (optional) - default 'general'.",
    },
    execute=_forget,
    required_permissions=["manage_messages"],
))
