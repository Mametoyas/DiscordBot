"""Thread skills (4): create/list/archive/delete."""

import discord

from . import Skill, register
from src.utils.fuzzy_match import find_channel


async def _find_thread(guild, query: str):
    """Active threads first, then archived (per-channel scan, best-effort)."""
    from src.utils.fuzzy_match import clean_input, extract_id, normalize_name

    raw = clean_input(query)
    if not raw:
        return None
    uid = extract_id(raw)
    threads = list(guild.threads)
    if uid:
        for t in threads:
            if str(t.id) == uid:
                return t
        try:
            th = await guild.fetch_channel(int(uid))
            if isinstance(th, discord.Thread):
                return th
        except (discord.NotFound, discord.HTTPException, ValueError):
            return None
    name = normalize_name(raw).lower()
    for t in threads:
        if t.name.lower() == name:
            return t
    for ch in guild.text_channels:
        try:
            async for t in ch.archived_threads(limit=50):
                if t.name.lower() == name:
                    return t
        except discord.HTTPException:
            continue
    for t in threads:
        if name in t.name.lower():
            return t
    return None


async def _create_thread(guild, params, message):
    name = (params.get("name") or "").strip()
    if not name:
        raise ValueError("ต้องมีชื่อเธรด (name)")
    if params.get("channelName"):
        channel = await find_channel(guild, params["channelName"])
        if not channel or not isinstance(channel, discord.TextChannel):
            raise ValueError(f"ไม่เจอห้องข้อความ \"{params['channelName']}\"")
    else:
        channel = message.channel if isinstance(message.channel, discord.TextChannel) else None
        if not channel:
            raise ValueError("ระบุ channelName มาด้วย (ห้องนี้สร้างเธรดไม่ได้)")
    msg = None
    if params.get("messageId"):
        try:
            msg = await channel.fetch_message(int(str(params["messageId"]).strip("<#@!>")))
        except (discord.NotFound, discord.HTTPException, ValueError):
            raise ValueError(f"ไม่เจอข้อความ ID {params['messageId']} ในห้องนี้")
    thread = await channel.create_thread(
        name=name, message=msg,
        auto_archive_duration=int(params.get("autoArchiveMinutes") or 1440),
        reason=f"Created by AI bot for {message.author}",
    )
    return f"สร้างเธรด **{thread.name}** ใน #{channel.name} แล้ว {thread.mention}"


register(Skill(
    name="createThread",
    description="Creates a thread in a text channel (optionally attached to a message).",
    params={
        "name": "string - Thread title.",
        "channelName": "string (optional) - Target text channel (default: current).",
        "messageId": "string (optional) - Start the thread from this message ID.",
        "autoArchiveMinutes": "number (optional) - 60/1440/4320/10080, default 1440.",
    },
    execute=_create_thread,
    required_permissions=["create_public_threads"],
))


async def _list_threads(guild, params, message):
    archived_only = str(params.get("archived", "")).lower() in ("true", "1", "yes")
    if params.get("channelName"):
        channel = await find_channel(guild, params["channelName"])
        if not channel or not isinstance(channel, discord.TextChannel):
            raise ValueError(f"ไม่เจอห้องข้อความ \"{params['channelName']}\"")
        channels = [channel]
    else:
        channels = list(guild.text_channels[:30])
    lines = []
    for ch in channels:
        active = [t for t in ch.threads] if not archived_only else []
        lines += [f"- {t.name} (active, {t.member_count or '?'} members) {t.mention}" for t in active]
        try:
            async for t in ch.archived_threads(limit=25):
                lines.append(f"- {t.name} (archived) {t.mention}")
        except discord.HTTPException:
            continue
    return "\n".join(lines) or "ไม่มีเธรดเลย"


register(Skill(
    name="listThreads",
    description="Lists active + archived threads, optionally for one channel.",
    params={
        "channelName": "string (optional) - Only this text channel.",
        "archived": "boolean (optional) - true = archived only.",
    },
    execute=_list_threads,
))


async def _archive_thread(guild, params, message):
    thread = await _find_thread(guild, params.get("threadName", ""))
    if not thread:
        raise ValueError(f"ไม่เจอเธรด \"{params.get('threadName')}\"")
    archived = params.get("archived", True)
    archived = archived if isinstance(archived, bool) else str(archived).lower() not in ("false", "0", "no")
    await thread.edit(archived=archived, reason=f"Archived by AI bot for {message.author}")
    return f"{'เก็บ' if archived else 'เปิด'}เธรด **{thread.name}** แล้ว"


register(Skill(
    name="archiveThread",
    description="Archives (or reopens with archived:false) a thread.",
    params={
        "threadName": "string - Thread name, mention, or ID.",
        "archived": "boolean (optional) - default true.",
    },
    execute=_archive_thread,
    required_permissions=["manage_threads"],
))


async def _delete_thread(guild, params, message):
    thread = await _find_thread(guild, params.get("threadName", ""))
    if not thread:
        raise ValueError(f"ไม่เจอเธรด \"{params.get('threadName')}\"")
    name = thread.name
    await thread.delete(reason=f"Deleted by AI bot for {message.author}")
    return f"ลบเธรด **{name}** แล้ว"


register(Skill(
    name="deleteThread",
    description="Deletes a thread.",
    params={"threadName": "string - Thread name, mention, or ID."},
    execute=_delete_thread,
    required_permissions=["manage_threads"],
    needs_confirm=True,
))
