"""Upgraded entity resolution — mirrors discord-bot-agents/src/utils/fuzzyMatch.js.

Resolve Discord entities from:
  - Mentions: <#ID> <@ID> <@!ID> <@&ID> <:name:ID> <a:name:ID>
  - Prefixed IDs: #123… @123… (LLMs often strip <> from mentions)
  - Raw snowflake IDs
  - Plain names (leading # / @ stripped; exact → case-insensitive → substring)
"""

import re

import discord

INVISIBLE = re.compile(r"[\u200b-\u200d\u2060\ufeff ]")
MENTION_RE = re.compile(r"<(?:#|@!?|@&|a?:\w+:)(\d+)>")
PREFIXED_ID_RE = re.compile(r"^[#@&]!?(\d{16,20})$")
SNOWFLAKE_RE = re.compile(r"^\d{16,20}$")


def clean_input(value) -> str:
    return INVISIBLE.sub("", str(value or "")).strip()


def extract_id(query: str) -> str | None:
    raw = clean_input(query)
    if not raw:
        return None
    m = MENTION_RE.search(raw)
    if m:
        return m.group(1)
    m = PREFIXED_ID_RE.match(raw)
    if m:
        return m.group(1)
    if SNOWFLAKE_RE.match(raw):
        return raw
    return None


def normalize_name(query: str) -> str:
    raw = clean_input(query)
    if not raw:
        return ""
    m = MENTION_RE.search(raw)
    if m:
        return m.group(1)
    return raw.lstrip("#@&")


def _closest(items: list, query: str, key=lambda x: x.name) -> object | None:
    """ID → exact → case-insensitive → substring (ID fetch NOT included)."""
    raw = clean_input(query)
    if not raw:
        return None
    uid = extract_id(raw)
    if uid:
        for it in items:
            if str(it.id) == uid:
                return it
    name = normalize_name(raw)
    if not name:
        return None
    if SNOWFLAKE_RE.match(name):
        for it in items:
            if str(it.id) == name:
                return it
    for it in items:
        if key(it) == name:
            return it
    low = name.lower()
    for it in items:
        if key(it).lower() == low:
            return it
    for it in items:
        if low in key(it).lower():
            return it
    return None


async def find_channel(guild: discord.Guild, query: str, kinds: tuple | None = None):
    channels = [c for c in guild.channels if kinds is None or c.type in kinds]
    hit = _closest(channels, query)
    if hit:
        return hit
    uid = extract_id(query)
    if uid:
        try:
            ch = await guild.fetch_channel(int(uid))
        except (discord.NotFound, discord.HTTPException, ValueError):
            return None
        if kinds is not None and ch.type not in kinds:
            return None
        return ch
    return None


def find_role(guild: discord.Guild, query: str):
    return _closest(list(guild.roles), query)


async def find_emoji(guild: discord.Guild, query: str):
    hit = _closest(list(guild.emojis), query)
    if hit:
        return hit
    uid = extract_id(query)
    if uid:
        try:
            return await guild.fetch_emoji(int(uid))
        except (discord.NotFound, discord.HTTPException, ValueError):
            return None
    return None


async def find_member(guild: discord.Guild, query: str):
    raw = clean_input(query)
    if not raw:
        return None
    uid = extract_id(raw)
    if uid:
        m = guild.get_member(int(uid))
        if m:
            return m
        try:
            return await guild.fetch_member(int(uid))
        except (discord.NotFound, discord.HTTPException, ValueError):
            return None
    name = normalize_name(raw)
    low = name.lower()
    for m in guild.members:
        if m.name.lower() == low or m.display_name.lower() == low:
            return m
    try:  # server-side username search (needs Server Members Intent)
        found = await guild.query_members(query=name, limit=1)
        if found:
            return found[0]
    except (discord.HTTPException, AttributeError):
        pass
    for m in guild.members:
        if low in m.display_name.lower() or low in m.name.lower():
            return m
    return None


TEXT_KINDS = (
    discord.ChannelType.text,
    discord.ChannelType.news,
    discord.ChannelType.forum,
)
