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


async def _check_db(guild, params, message):
    """Truthful database health check — never claim ok without probing."""
    if not store.enabled:
        return ("❌ ยังไม่ได้ตั้งค่า SUPABASE_URL/SUPABASE_KEY — "
                "ตอนนี้จำได้แค่ในเครื่อง (restart หาย)")
    import httpx

    tables = ["chat_history", "member_aliases", "memories"]
    lines = []
    ok_all = True
    async with httpx.AsyncClient(timeout=10.0) as c:
        for t in tables:
            try:
                r = await c.get(f"{store.url}/rest/v1/{t}",
                                headers=store._headers(),
                                params={"select": "id", "limit": 1})
                if r.status_code == 200:
                    lines.append(f"✅ {t}")
                elif r.status_code == 404:
                    ok_all = False
                    lines.append(f"❌ {t} — ยังไม่สร้างตาราง (รัน SQL ใน chat_store.py)")
                else:
                    ok_all = False
                    lines.append(f"⚠️ {t} — HTTP {r.status_code}")
            except Exception as e:  # noqa: BLE001
                ok_all = False
                lines.append(f"⚠️ {t} — ต่อไม่ได้: {e}")
    head = "🟢 ฐานข้อมูลปกติ" if ok_all else "🔴 ฐานข้อมูลมีปัญหา"
    return head + "\n" + "\n".join(lines)


register(Skill(
    name="checkDatabase",
    description="Checks whether the Supabase tables (chat_history, member_aliases, memories) actually exist and respond.",
    params={"format": "string (optional) - reserved, currently ignored."},
    execute=_check_db,
))
