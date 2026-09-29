"""Emoji skills (4) + invite skills (3)."""

import re

import discord
import httpx

from . import Skill, register

_EMOJI_NAME = re.compile(r"^[A-Za-z0-9_]{2,32}$")


async def _list_emojis(guild, params, message):
    if not guild.emojis:
        return "This server has no custom emojis."
    return "\n".join(f"- {e.name} {e} (ID: {e.id})" for e in guild.emojis)


async def _list_emojis_raw(guild, message):
    return {"total": len(guild.emojis), "names": [e.name for e in guild.emojis[:50]]}


register(Skill(
    name="listEmojis",
    description="Lists all custom emojis in the server.",
    params={},
    execute=_list_emojis,
    fetch_raw=_list_emojis_raw,
))


async def _create_emoji(guild, params, message):
    name, url = params.get("name"), params.get("url")
    if not name or not url:
        raise ValueError("I need both an emoji name and an image URL.")
    if not _EMOJI_NAME.match(name):
        raise ValueError("Emoji names must be 2-32 chars: letters, numbers, underscores only.")
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
        r.raise_for_status()
        image = r.content
    if len(image) > 256 * 1024:
        raise ValueError("That image is over 256KB — Discord won't accept it.")
    emoji = await guild.create_custom_emoji(
        name=name, image=image, reason=params.get("reason") or f"Created by AI bot for {message.author}"
    )
    return f"Emoji {emoji} created."


register(Skill(
    name="createEmoji",
    description="Creates a custom emoji from a name and an image URL.",
    params={
        "name": "string - 2-32 chars, letters/numbers/underscore.",
        "url": "string - Direct image URL.",
        "reason": "string (optional).",
    },
    execute=_create_emoji,
    required_permissions=["manage_emojis_and_stickers"],
))


async def _edit_emoji(guild, params, message):
    emoji = discord.utils.get(guild.emojis, name=params.get("currentName"))
    if not emoji:
        raise ValueError(f"I couldn't find an emoji called \"{params.get('currentName')}\".")
    new_name = params.get("newName", "")
    if not new_name or not _EMOJI_NAME.match(new_name):
        raise ValueError("New name must be 2-32 chars: letters, numbers, underscores only.")
    await emoji.edit(name=new_name, reason=params.get("reason") or f"Renamed by AI bot for {message.author}")
    return True


register(Skill(
    name="editEmoji",
    description="Renames a custom emoji.",
    params={
        "currentName": "string - Current emoji name.",
        "newName": "string - New emoji name.",
        "reason": "string (optional).",
    },
    execute=_edit_emoji,
    required_permissions=["manage_emojis_and_stickers"],
))


async def _delete_emoji(guild, params, message):
    emoji = discord.utils.get(guild.emojis, name=params.get("emojiName"))
    if not emoji:
        raise ValueError(f"I couldn't find an emoji called \"{params.get('emojiName')}\".")
    await emoji.delete(reason=params.get("reason") or f"Deleted by AI bot for {message.author}")
    return True


register(Skill(
    name="deleteEmoji",
    description="Deletes a custom emoji.",
    params={
        "emojiName": "string - Emoji name.",
        "reason": "string (optional).",
    },
    execute=_delete_emoji,
    required_permissions=["manage_emojis_and_stickers"],
))
