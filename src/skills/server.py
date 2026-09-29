"""Server/misc skills (6): info/edit/search/send/snipe/setup."""

import discord

from . import Skill, register
from src.utils.fuzzy_match import TEXT_KINDS, find_channel
from src.utils.snipe_manager import get_snipes


async def _get_server_info(guild, params, message):
    return (
        f"**{guild.name}**\nID: {guild.id}\nOwner: {guild.owner} ({guild.owner_id})\n"
        f"Members: {guild.member_count} | Channels: {len(guild.channels)} | "
        f"Roles: {len(guild.roles)} | Emojis: {len(guild.emojis)}\n"
        f"Verification: {guild.verification_level} | Created: {guild.created_at:%Y-%m-%d}"
    )


async def _get_server_info_raw(guild, message):
    return {
        "name": guild.name, "id": guild.id,
        "owner": str(guild.owner), "ownerId": guild.owner_id,
        "members": guild.member_count, "channels": len(guild.channels),
        "roles": len(guild.roles), "emojis": len(guild.emojis),
    }


register(Skill(
    name="getServerInfo",
    description="Shows server overview (owner, counts, verification, creation date).",
    params={},
    execute=_get_server_info,
    fetch_raw=_get_server_info_raw,
))


async def _edit_server(guild, params, message):
    kwargs: dict = {"reason": f"Edited by AI bot for {message.author}"}
    if params.get("name"):
        kwargs["name"] = params["name"]
    if params.get("description") is not None:
        kwargs["description"] = params["description"]
    if params.get("verificationLevel") is not None:
        try:
            kwargs["verification_level"] = discord.VerificationLevel(int(params["verificationLevel"]))
        except (TypeError, ValueError):
            raise ValueError("verificationLevel must be 0-4.")
    if params.get("afkChannelName"):
        ch = await find_channel(
            guild, params["afkChannelName"],
            kinds=(discord.ChannelType.voice, discord.ChannelType.stage_voice),
        )
        if not ch:
            raise ValueError(f"I couldn't find a voice channel called \"{params['afkChannelName']}\".")
        kwargs["afk_channel"] = ch
    if params.get("afkTimeout") is not None:
        kwargs["afk_timeout"] = int(params["afkTimeout"])
    if len(kwargs) == 1:
        raise ValueError("Nothing to change — give me a name, description, or setting.")
    await guild.edit(**kwargs)
    return True


register(Skill(
    name="editServer",
    description="Edits server name, description, verification level, or AFK settings.",
    params={
        "name": "string (optional) - New server name.",
        "description": "string (optional).",
        "verificationLevel": "number (optional) - 0 None … 4 Very High.",
        "afkChannelName": "string (optional).",
        "afkTimeout": "number (optional) - Seconds.",
    },
    execute=_edit_server,
    required_permissions=["manage_guild"],
))


async def _search_server(guild, params, message):
    q = (params.get("query") or "").strip().lower().lstrip("#@")
    if not q:
        raise ValueError("I need something to search for.")
    out = []
    chs = [c for c in guild.channels if q in c.name.lower()][:5]
    if chs:
        out.append("Channels: " + ", ".join(f"#{c.name} {c.mention}" for c in chs))
    roles = [r for r in guild.roles if not r.is_default() and q in r.name.lower()][:5]
    if roles:
        out.append("Roles: " + ", ".join(r.name for r in roles))
    members = [m for m in guild.members
               if q in m.display_name.lower() or q in m.name.lower()][:5]
    if members:
        out.append("Members: " + ", ".join(m.display_name for m in members))
    return "\n".join(out) or f'Nothing matching "{params.get("query")}" found.'


register(Skill(
    name="searchServer",
    description="Fuzzy-searches channels, roles, and members by name.",
    params={"query": "string - What to search for."},
    execute=_search_server,
))


async def _send_message(guild, params, message):
    if not params.get("channelName") or not params.get("content"):
        raise ValueError("I need both a channel name and the message content to send.")
    channel = await find_channel(guild, params["channelName"], kinds=TEXT_KINDS)
    if not channel:
        raise ValueError(f"I couldn't find a text channel called \"{params['channelName']}\" here.")
    if getattr(channel, "nsfw", False) and not message.channel.nsfw:
        raise ValueError(
            f'You can\'t send messages to the age-restricted channel "{channel.name}" from a public channel.'
        )
    bot_perms = channel.permissions_for(guild.me)
    if not bot_perms.view_channel or not bot_perms.send_messages:
        raise ValueError(f"I don't have permission to see or send messages in #{channel.name}.")
    if message.author.id != guild.owner_id:
        user_perms = channel.permissions_for(message.author)
        if not user_perms.view_channel or not user_perms.send_messages:
            raise ValueError(f"You don't have permission to see or send messages in #{channel.name}.")
    await channel.send(params["content"][:2000])
    return True


register(Skill(
    name="sendMessage",
    description="Sends a message to a target channel.",
    params={
        "channelName": "string - Channel name, mention, or ID.",
        "content": "string - Message content.",
    },
    execute=_send_message,
    required_permissions=["send_messages"],
))


async def _get_snipe(guild, params, message):
    channel = message.channel
    if params.get("channelName"):
        channel = await find_channel(guild, params["channelName"], kinds=TEXT_KINDS)
        if not channel:
            raise ValueError(f"I couldn't find a text channel called \"{params['channelName']}\".")
    q = get_snipes(channel.id)
    if not q:
        return "Nothing deleted there recently."
    s = q[0]
    return f"**{s['author']}** deleted at {s['at']:%H:%M}:\n{s['content'] or '(no text)'}"


register(Skill(
    name="getSnipe",
    description="Shows the most recently deleted message in a channel.",
    params={"channelName": "string (optional) - Defaults to current channel."},
    execute=_get_snipe,
))


STYLE_KEYWORDS = {
    "gaming": ("minecraft", "มายคราฟ", "valorant", "pubg", "พับจี", "game", "เกม",
               "lfp", "party", "clip", "คลิป", "เล่น"),
    "study": ("study", "homework", "เรียน", "หนังสือ", "code", "script", "program",
              "it", "ai", "knowledge", "ux", "ontology", "หุ้น", "work", "งาน",
              "project", "โปรเจกต์", "resource"),
}

STYLE_TEMPLATES = {
    "study": [("general", "text"), ("study-room", "text"), ("resources", "text"),
              ("welcome", "text"), ("Study Lounge", "voice")],
    "gaming": [("general", "text"), ("looking-for-party", "text"), ("clips", "text"),
               ("welcome", "text"), ("Game Lobby", "voice")],
    "community": [("general", "text"), ("rules", "text"), ("welcome", "text"),
                  ("Chill Lounge", "voice")],
}


def _detect_style(guild) -> str:
    """Pick template from existing channel names (user asked: adapt, don't default)."""
    names = " ".join(c.name.lower() for c in guild.channels)
    scores = {s: sum(1 for kw in kws if kw in names)
              for s, kws in STYLE_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "community"


async def _setup_server(guild, params, message):
    """Create a standard layout (never deletes anything, skips existing)."""
    asked = str(params.get("style", "")).lower()
    if "study" in asked or "เรียน" in asked:
        style = "study"
    elif "gam" in asked or "เกม" in asked:
        style = "gaming"
    elif "commun" in asked:
        style = "community"
    else:
        style = _detect_style(guild)  # no explicit style -> adapt to this server
    plan = STYLE_TEMPLATES[style]
    made, skipped = [], []
    welcome_ch = None
    for name, kind in plan:
        exists = await find_channel(guild, name)
        if exists:
            skipped.append(name)
            if name == "welcome":
                welcome_ch = exists
            continue
        if kind == "voice":
            ch = await guild.create_voice_channel(
                name, reason=f"setupServer by AI bot for {message.author}")
        else:
            ch = await guild.create_text_channel(
                name, reason=f"setupServer by AI bot for {message.author}")
        made.append(name)
        if name == "welcome":
            welcome_ch = ch
    if welcome_ch and isinstance(welcome_ch, discord.TextChannel):
        try:
            await welcome_ch.send(
                f"🎉 ยินดีต้อนรับสู่ **{guild.name}**!\n"
                "• เริ่มที่ห้อง rules อ่านกติกาก่อนนะ\n"
                "• คุยเล่นที่ห้อง general\n"
                "• อยากคุยเสียง เข้าห้องเสียงด้านล่างได้เลย")
        except discord.HTTPException:
            pass
    parts = [f"สไตล์ที่เลือก: {style}"]
    if made:
        parts.append("สร้างแล้ว: " + ", ".join(f"#{m}" for m in made))
    if skipped:
        parts.append("มีอยู่แล้ว ข้าม: " + ", ".join(f"#{s}" for s in skipped))
    return "\n".join(parts) or "ไม่มีอะไรต้องทำ"


register(Skill(
    name="setupServer",
    description="Sets up channels adapted to THIS server: scans existing channel names and picks community/gaming/study template automatically (explicit style param overrides). Never deletes, skips existing, posts welcome message.",
    params={"style": "string (optional) - community, gaming, study, or empty = auto-detect."},
    execute=_setup_server,
    required_permissions=["manage_channels"],
))
