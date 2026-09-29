"""Member skills (5): info/nickname/move/mute/deafen."""

import discord

from . import Skill, register
from src.utils.fuzzy_match import find_channel, find_member


async def _get_user_info(guild, params, message):
    member = await find_member(guild, params.get("memberId", ""))
    if not member:
        raise ValueError(f"I couldn't find anyone matching \"{params.get('memberId')}\" here.")
    roles = ", ".join(r.name for r in member.roles if not r.is_default()) or "-"
    joined = member.joined_at.strftime("%Y-%m-%d %H:%M") if member.joined_at else "-"
    created = member.created_at.strftime("%Y-%m-%d")
    lines = [
        f"**{member.display_name}** ({member})",
        f"ID: {member.id} | Mention: {member.mention}",
        f"Joined server: {joined} | Account created: {created}",
        f"Roles: {roles}",
        f"Timed out: {'yes until ' + str(member.timed_out_until) if member.is_timed_out() else 'no'}",
    ]
    return "\n".join(lines)


register(Skill(
    name="getUserInfo",
    description="Shows profile info about a member (join dates, roles, timeout state).",
    params={"memberId": "string - The ID, mention, or username of the member."},
    execute=_get_user_info,
))


async def _set_nickname(guild, params, message):
    member = await find_member(guild, params.get("memberId", ""))
    if not member:
        raise ValueError(f"I couldn't find anyone matching \"{params.get('memberId')}\" here.")
    nick = params.get("nickname", "")
    await member.edit(nick=nick or None, reason=f"Nickname set by AI bot for {message.author}")
    return True


register(Skill(
    name="setNickname",
    description='Sets a member nickname (empty string "" resets it).',
    params={
        "memberId": "string - The ID, mention, or username of the member.",
        "nickname": 'string (optional) - New nickname, "" resets.',
        "reason": "string (optional).",
    },
    execute=_set_nickname,
    required_permissions=["manage_nicknames"],
    targets_member=True,
))


async def _move_member(guild, params, message):
    member = await find_member(guild, params.get("memberId", ""))
    if not member:
        raise ValueError(f"I couldn't find anyone matching \"{params.get('memberId')}\" here.")
    target = None
    if params.get("channelId"):
        target = find_channel(
            guild, params["channelId"], kinds=(discord.ChannelType.voice, discord.ChannelType.stage_voice)
        )
        if not target:
            raise ValueError(f"I couldn't find a voice channel called \"{params['channelId']}\".")
    await member.move_to(target, reason=f"Moved by AI bot for {message.author}")
    return True


register(Skill(
    name="moveMember",
    description="Moves a member between voice channels (omit channelId to disconnect).",
    params={
        "memberId": "string - The ID, mention, or username of the member.",
        "channelId": "string (optional) - Target voice channel name/mention/ID; empty = disconnect.",
    },
    execute=_move_member,
    required_permissions=["move_members"],
    targets_member=True,
))


async def _mute_member(guild, params, message):
    member = await find_member(guild, params.get("memberId", ""))
    if not member:
        raise ValueError(f"I couldn't find anyone matching \"{params.get('memberId')}\" here.")
    mute = params.get("mute", True)
    mute = mute if isinstance(mute, bool) else str(mute).lower() not in ("false", "0", "no")
    await member.edit(mute=mute, reason=params.get("reason") or f"Muted by AI bot for {message.author}")
    return True


register(Skill(
    name="muteMember",
    description="Server-mutes (or unmutes with mute:false) a member's microphone.",
    params={
        "memberId": "string - The ID, mention, or username of the member.",
        "mute": "boolean (optional) - true to mute, false to unmute (default true).",
        "reason": "string (optional).",
    },
    execute=_mute_member,
    required_permissions=["mute_members"],
    targets_member=True,
))


async def _deafen_member(guild, params, message):
    member = await find_member(guild, params.get("memberId", ""))
    if not member:
        raise ValueError(f"I couldn't find anyone matching \"{params.get('memberId')}\" here.")
    deaf = params.get("deaf", True)
    deaf = deaf if isinstance(deaf, bool) else str(deaf).lower() not in ("false", "0", "no")
    await member.edit(deafen=deaf, reason=params.get("reason") or f"Deafened by AI bot for {message.author}")
    return True


register(Skill(
    name="deafenMember",
    description="Server-deafens (or undeafens with deaf:false) a member.",
    params={
        "memberId": "string - The ID, mention, or username of the member.",
        "deaf": "boolean (optional) - true to deafen, false to undeafen (default true).",
        "reason": "string (optional).",
    },
    execute=_deafen_member,
    required_permissions=["deafen_members"],
    targets_member=True,
))
