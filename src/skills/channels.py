"""Channel skills (7): create/delete/edit/list/info/category/restructure."""

import discord

from . import Skill, register
from src.utils.fuzzy_match import TEXT_KINDS, find_channel, find_role

TYPE_MAP = {
    discord.ChannelType.text: "Text",
    discord.ChannelType.voice: "Voice",
    discord.ChannelType.category: "Category",
    discord.ChannelType.news: "Announcement",
    discord.ChannelType.stage_voice: "Stage",
    discord.ChannelType.forum: "Forum",
}


async def _create_channel(guild, params, message):
    name = params.get("name")
    if not name:
        raise ValueError("I need a name for the channel first.")
    kind = "voice" if str(params.get("type", "text")).lower() == "voice" else "text"
    kwargs: dict = {"name": name, "reason": f"Created by AI bot for {message.author}"}
    warning = None
    if params.get("categoryName"):
        cat = await find_channel(guild, params["categoryName"], kinds=(discord.ChannelType.category,))
        if cat:
            kwargs["parent"] = cat
        else:
            warning = f"I couldn't find a category matching \"{params['categoryName']}\" — the channel was created without one."
    if params.get("topic") and kind == "text":
        kwargs["topic"] = params["topic"]
    if params.get("ageRestricted"):
        kwargs["nsfw"] = True
    if params.get("position") is not None:
        kwargs["position"] = int(params["position"])
    if kind == "voice":
        await guild.create_voice_channel(**kwargs)
    else:
        await guild.create_text_channel(**kwargs)
    return warning or True


register(Skill(
    name="createChannel",
    description="Creates a new text or voice channel, optionally within a specific category.",
    params={
        "name": "string - channel name",
        "type": 'string - "text" or "voice" (default: text)',
        "categoryName": "string (optional) - category name",
        "topic": "string (optional) - channel topic (for text channels)",
        "ageRestricted": "boolean (optional) - default false",
        "position": "number (optional)",
    },
    execute=_create_channel,
    required_permissions=["manage_channels"],
))


async def _delete_channel(guild, params, message):
    ch = await find_channel(guild, params.get("channelName", ""))
    if not ch:
        raise ValueError(f"I couldn't find a channel called \"{params.get('channelName')}\" here.")
    await ch.delete(reason=f"Deleted by AI bot for {message.author}")
    return True


register(Skill(
    name="deleteChannel",
    description="Deletes a channel from the server.",
    params={"channelName": "string - The name, mention, or ID of the channel to delete."},
    execute=_delete_channel,
    required_permissions=["manage_channels"],
))


async def _edit_channel(guild, params, message):
    ch = await find_channel(guild, params.get("currentName", ""))
    if not ch:
        raise ValueError(f"I couldn't find a channel called \"{params.get('currentName')}\" here.")
    kwargs: dict = {"reason": f"Edited by AI bot for {message.author}"}
    if params.get("newName"):
        kwargs["name"] = params["newName"]
    if params.get("topic") is not None and ch.type in TEXT_KINDS:
        kwargs["topic"] = params["topic"]
    if params.get("position") is not None:
        kwargs["position"] = int(params["position"])
    if params.get("parentCategory"):
        cat = await find_channel(guild, params["parentCategory"], kinds=(discord.ChannelType.category,))
        if not cat:
            raise ValueError(f"I couldn't find a category called \"{params['parentCategory']}\".")
        kwargs["category"] = cat
    if params.get("ageRestricted") is not None and ch.type in TEXT_KINDS:
        kwargs["nsfw"] = bool(params["ageRestricted"])
    if params.get("private") is not None or params.get("allowRoles"):
        overwrites = dict(ch.overwrites)
        if params.get("private") is not None:
            ow = overwrites.get(guild.default_role, discord.PermissionOverwrite())
            ow.view_channel = None if not params["private"] else False
            overwrites[guild.default_role] = ow
        for rname in (params.get("allowRoles") or []):
            role = find_role(guild, rname)
            if role:
                ow = overwrites.get(role, discord.PermissionOverwrite())
                ow.view_channel = True
                ow.send_messages = True
                ow.connect = True
                overwrites[role] = ow
        kwargs["overwrites"] = overwrites
    await ch.edit(**kwargs)
    return True


register(Skill(
    name="editChannel",
    description="Edits the name, topic, position, category, age restriction, privacy (private hides from @everyone), or role access of a channel.",
    params={
        "currentName": "string - The current name, mention, or ID of the channel.",
        "newName": "string (optional) - New channel name.",
        "topic": "string (optional) - New topic (text channels).",
        "position": "number (optional) - New position.",
        "parentCategory": "string (optional) - Move to this category.",
        "ageRestricted": "boolean (optional) - Set age restriction.",
        "private": "boolean (optional) - true hides channel from @everyone, false unhides.",
        "allowRoles": "array (optional) - Role names to grant view/send/connect.",
    },
    execute=_edit_channel,
    required_permissions=["manage_channels"],
))


async def _list_channels(guild, params, message):
    fmt = str(params.get("format", "list")).lower()
    type_filter = str(params.get("type", "")).lower() or None
    cat_filter = str(params.get("categoryName", "")).lower() or None

    def keep(ch):
        if type_filter and TYPE_MAP.get(ch.type, "unknown").lower() != type_filter:
            return False
        if cat_filter and not (
            getattr(ch, "category", None) and cat_filter in ch.category.name.lower()
        ):
            return False
        return True

    channels = sorted(
        [c for c in guild.channels if keep(c)],
        key=lambda c: (c.position, c.name),
    )
    if not channels:
        return "No channels match what you're looking for."
    if fmt == "tree":
        lines = []
        for cat in [c for c in channels if c.type == discord.ChannelType.category]:
            lines.append(f"**{cat.name}**")
            for child in [c for c in channels if getattr(c, "category_id", None) == cat.id]:
                lines.append(f" - {child.name} ({TYPE_MAP.get(child.type, '?')}) {child.mention}")
        lone = [c for c in channels
                if c.type != discord.ChannelType.category and getattr(c, "category_id", None) is None]
        for ch in lone:
            lines.append(f"- {ch.name} ({TYPE_MAP.get(ch.type, '?')}) {ch.mention}")
        return "\n".join(lines)
    return "\n".join(
        f"- {c.name} ({TYPE_MAP.get(c.type, '?')}) - {c.mention}" for c in channels
    )


async def _list_channels_raw(guild, message):
    return {
        "total": len(guild.channels),
        "names": [c.name for c in guild.channels[:50]],
    }


register(Skill(
    name="listChannels",
    description="Lists all channels in the server. Returns raw data for AI to format.",
    params={
        "type": 'string (optional) - Filter by channel type: "text", "voice", "category".',
        "categoryName": "string (optional) - Only channels under this category.",
        "format": 'string (optional) - "list" (default, flat list) or "tree" (organized by category).',
    },
    execute=_list_channels,
    fetch_raw=_list_channels_raw,
))


async def _get_channel_info(guild, params, message):
    ch = await find_channel(guild, params.get("channelName", ""))
    if not ch:
        raise ValueError(f"I couldn't find a channel called \"{params.get('channelName')}\" here.")
    lines = [
        f"**{ch.name}** ({TYPE_MAP.get(ch.type, '?')})",
        f"ID: {ch.id} | Mention: {ch.mention}",
    ]
    if ch.type in TEXT_KINDS:
        lines.append(f"Topic: {ch.topic or '-'} | NSFW: {ch.nsfw}")
    cat = getattr(ch, "category", None)
    if cat:
        lines.append(f"Category: {cat.name}")
    lines.append(f"Position: {ch.position}")
    return "\n".join(lines)


register(Skill(
    name="getChannelInfo",
    description="Shows detailed info about one channel (topic, category, position, NSFW).",
    params={"channelName": "string - The name, mention, or ID of the channel."},
    execute=_get_channel_info,
))


def _clean_name(name: str) -> str:
    """Discord channel names: lowercase, spaces -> dashes, max 100 chars."""
    return str(name or "").strip().lower().replace(" ", "-")[:100]


async def _create_category(guild, params, message):
    name = (params.get("name") or "").strip()
    if not name:
        raise ValueError("I need a name for the category first.")
    exists = await find_channel(
        guild, name, kinds=(discord.ChannelType.category,))
    if exists:
        return f"Category **{exists.name}** already exists."
    cat = await guild.create_category(
        name, reason=f"Created by AI bot for {message.author}")
    return f"Category **{cat.name}** created."


register(Skill(
    name="createCategory",
    description="Creates a channel category (existing name returns as-is, no duplicate).",
    params={"name": "string - Category name."},
    execute=_create_category,
    required_permissions=["manage_channels"],
))


async def _restructure(guild, params, message):
    """Build whole layout in ONE action (bypasses the 5-action plan cap).

    layout = list of {name, text: [names], voice: [names], private: bool}
    (or JSON string). Creates missing categories/channels, moves existing
    channels in, applies privacy. Never deletes.
    """
    import json as _json

    layout = params.get("layout")
    if isinstance(layout, str):
        try:
            layout = _json.loads(layout)
        except ValueError:
            raise ValueError("Layout ไม่ใช่ JSON ที่อ่านได้ — ลองใหม่อีกที")
    if not isinstance(layout, list) or not layout:
        raise ValueError("I need a layout: list of {name, text:[...], voice:[...]}.")
    created, moved, skipped = [], [], []
    for block in layout[:8]:  # safety cap
        if not isinstance(block, dict) or not block.get("name"):
            continue
        cat = await find_channel(
            guild, block["name"], kinds=(discord.ChannelType.category,))
        if not cat:
            cat = await guild.create_category(
                block["name"].strip(),
                reason=f"restructureServer by AI bot for {message.author}")
            created.append(f"📁 {cat.name}")
        if block.get("private"):
            ow = dict(cat.overwrites)
            ow[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
            await cat.edit(
                overwrites=ow,
                reason=f"restructureServer private by AI bot for {message.author}")
            created.append(f"🔒 {cat.name} (private)")
        for kind, is_voice in (("text", False), ("voice", True)):
            for raw in (block.get(kind) or [])[:20]:
                name = _clean_name(raw)
                if not name:
                    continue
                kinds = ((discord.ChannelType.voice, discord.ChannelType.stage_voice)
                         if is_voice else TEXT_KINDS)
                ch = await find_channel(guild, raw) or await find_channel(guild, name)
                try:
                    if ch:
                        if getattr(ch, "category_id", None) != cat.id:
                            await ch.edit(
                                category=cat,
                                reason=f"restructureServer by AI bot for {message.author}")
                            moved.append(f"{'🔊' if is_voice else '#️⃣'} {ch.name}")
                        else:
                            skipped.append(ch.name)
                    elif is_voice:
                        ch = await guild.create_voice_channel(
                            name, category=cat,
                            reason=f"restructureServer by AI bot for {message.author}")
                        created.append(f"🔊 {name}")
                    else:
                        ch = await guild.create_text_channel(
                            name, category=cat,
                            reason=f"restructureServer by AI bot for {message.author}")
                        created.append(f"#️⃣ {name}")
                except discord.HTTPException:
                    skipped.append(f"{name} (สร้างไม่ได้)")
    parts = []
    if created:
        parts.append("สร้างแล้ว:\n" + "\n".join(f"- {c}" for c in created))
    if moved:
        parts.append("ย้ายแล้ว:\n" + "\n".join(f"- {c}" for c in moved))
    if skipped:
        parts.append("มีอยู่แล้ว ข้าม: " + ", ".join(skipped))
    return "\n".join(parts) or "ไม่มีอะไรต้องทำ"


register(Skill(
    name="restructureServer",
    description="Reorganizes the server in ONE call: creates categories (private:true hides from @everyone), creates missing text/voice channels inside them, moves existing channels in. Takes a full layout, never deletes anything.",
    params={"layout": "array - [{name: category, text: [...], voice: [...], private: true/false}]."},
    execute=_restructure,
    required_permissions=["manage_channels"],
))
