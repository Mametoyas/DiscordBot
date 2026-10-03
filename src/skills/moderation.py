"""Moderation skills (5): kick/ban/unban/timeout/purge."""

from datetime import timedelta

import discord

from . import Skill, register
from src.utils.fuzzy_match import TEXT_KINDS, find_channel, find_member


async def _remove_member(guild, params, message):
    member = await find_member(guild, params.get("memberId", ""))
    if not member:
        raise ValueError(f"I couldn't find anyone matching \"{params.get('memberId')}\" here.")
    await member.kick(reason=params.get("reason") or f"Kicked by AI bot for {message.author}")
    return True


register(Skill(
    name="removeMember",
    description="Kicks a member from the server.",
    params={
        "memberId": "string - The ID, mention, or username of the member to kick.",
        "reason": "string (optional).",
    },
    execute=_remove_member,
    required_permissions=["kick_members"],
    targets_member=True,
    needs_confirm=True,
))


async def _block_member(guild, params, message):
    member = await find_member(guild, params.get("memberId", ""))
    if not member:
        raise ValueError(f"I couldn't find anyone matching \"{params.get('memberId')}\" here.")
    days = int(params.get("deleteMessageDays", 0) or 0)
    days = max(0, min(7, days))
    await member.ban(
        reason=params.get("reason") or f"Banned by AI bot for {message.author}",
        delete_message_days=days,
    )
    return True


register(Skill(
    name="blockMember",
    description="Bans a member from the server.",
    params={
        "memberId": "string - The ID, mention, or username of the member to ban.",
        "reason": "string (optional).",
        "deleteMessageDays": "number (optional) - Delete recent messages, 0-7 (default 0).",
    },
    execute=_block_member,
    required_permissions=["ban_members"],
    targets_member=True,
    needs_confirm=True,
))


async def _unblock_member(guild, params, message):
    raw = (params.get("memberId") or "").strip()
    uid = "".join(c for c in raw if c.isdigit())
    if not uid:
        raise ValueError("I need a user ID to unban.")
    try:
        user = await guild.fetch_ban(discord.Object(id=int(uid)))
        await guild.unban(user.user, reason=params.get("reason") or f"Unbanned by AI bot for {message.author}")
    except discord.NotFound:
        raise ValueError(f"User `{uid}` is not banned here.")
    return True


register(Skill(
    name="unblockMember",
    description="Unbans a user by ID.",
    params={
        "memberId": "string - The user ID to unban.",
        "reason": "string (optional).",
    },
    execute=_unblock_member,
    required_permissions=["ban_members"],
))


async def _timeout_member(guild, params, message):
    member = await find_member(guild, params.get("memberId", ""))
    if not member:
        raise ValueError(f"I couldn't find anyone matching \"{params.get('memberId')}\" here.")
    minutes = params.get("durationMinutes", 5)
    try:
        minutes = float(minutes)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid duration: {params.get('durationMinutes')}.")
    if minutes <= 0:
        if not member.is_timed_out():
            raise ValueError(f"{member.display_name} isn't currently timed out, nothing to remove.")
        await member.timeout(None, reason=params.get("reason") or f"Timeout removed by AI bot for {message.author}")
        return True
    if member.is_timed_out():
        raise ValueError(f"{member.display_name} is already timed out until {member.timed_out_until} — pick another member or wait.")
    await member.timeout(
        timedelta(minutes=minutes),
        reason=params.get("reason") or f"Timed out by AI bot for {message.author}",
    )
    return True


register(Skill(
    name="timeoutMember",
    description="Times out a member for N minutes (0 removes; 40320 = forever).",
    params={
        "memberId": "string - The ID, mention, or username of the member.",
        "durationMinutes": "number (optional) - Minutes, default 5. 0 removes the timeout.",
        "reason": "string (optional).",
    },
    execute=_timeout_member,
    required_permissions=["moderate_members"],
    targets_member=True,
))


async def _clear_messages(guild, params, message):
    try:
        count = int(params.get("count", 0))
    except (TypeError, ValueError):
        raise ValueError("I need a message count between 1 and 100.")
    if not 1 <= count <= 100:
        raise ValueError("Count must be between 1 and 100.")
    channel = message.channel
    if params.get("channelName"):
        channel = await find_channel(guild, params["channelName"], kinds=TEXT_KINDS)
        if not channel:
            raise ValueError(f"I couldn't find a text channel called \"{params['channelName']}\".")
    target_id = None
    if params.get("memberId"):
        member = await find_member(guild, params["memberId"])
        if not member:
            raise ValueError(f"I couldn't find anyone matching \"{params['memberId']}\".")
        target_id = member.id

    def check(m):
        return target_id is None or m.author.id == target_id

    deleted = await channel.purge(limit=count, check=check)
    return f"Deleted {len(deleted)} message(s)."


register(Skill(
    name="clearMessages",
    description="Bulk-deletes recent messages (1-100), optionally only from one member.",
    params={
        "count": "number - How many recent messages to delete (1-100).",
        "memberId": "string (optional) - Only delete this member's messages.",
        "channelName": "string (optional) - Target channel (default: current).",
    },
    execute=_clear_messages,
    required_permissions=["manage_messages"],
    needs_confirm=True,
))
