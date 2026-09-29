"""Invite skills (3): create/list/delete."""

from . import Skill, register
from src.utils.fuzzy_match import TEXT_KINDS, find_channel


async def _create_invite(guild, params, message):
    channel = await find_channel(guild, params.get("channelName", ""), kinds=TEXT_KINDS)
    if not channel:
        raise ValueError(f"I couldn't find a text channel called \"{params.get('channelName')}\".")
    invite = await channel.create_invite(
        max_age=int(params.get("maxAge", 86400) or 0),
        max_uses=int(params.get("maxUses", 0) or 0),
        temporary=bool(params.get("temporary", False)),
        reason=params.get("reason") or f"Created by AI bot for {message.author}",
    )
    return str(invite.url)


register(Skill(
    name="createInvite",
    description="Creates an invite link for a channel (maxAge 0 = permanent).",
    params={
        "channelName": "string - Target channel name/mention/ID.",
        "maxAge": "number (optional) - Seconds, 0 = permanent (default 86400).",
        "maxUses": "number (optional) - 0 = unlimited.",
        "temporary": "boolean (optional).",
        "reason": "string (optional).",
    },
    execute=_create_invite,
    required_permissions=["create_instant_invite"],
))


async def _list_invites(guild, params, message):
    invites = await guild.invites()
    if not invites:
        return "There are no active invites."
    return "\n".join(
        f"- {inv.code}: #{inv.channel} by {inv.inviter} ({inv.uses}/{inv.max_uses or '∞'} uses)"
        for inv in invites
    )


async def _list_invites_raw(guild, message):
    invites = await guild.invites()
    return {"total": len(invites), "codes": [inv.code for inv in invites[:20]]}


register(Skill(
    name="listInvites",
    description="Lists active server invites with usage.",
    params={},
    execute=_list_invites,
    required_permissions=["manage_guild"],
    fetch_raw=_list_invites_raw,
))


async def _delete_invite(guild, params, message):
    code = (params.get("inviteCode") or "").strip().rsplit("/", 1)[-1]
    if not code:
        raise ValueError("I need an invite code or URL.")
    invite = discord.utils.get(await guild.invites(), code=code)
    if invite is None:
        raise ValueError(f"I couldn't find an invite `{code}`.")
    await invite.delete(reason=f"Deleted by AI bot for {message.author}")
    return True


register(Skill(
    name="deleteInvite",
    description="Deletes an invite by code or URL.",
    params={"inviteCode": "string - Invite code or full URL."},
    execute=_delete_invite,
    required_permissions=["manage_guild"],
))
