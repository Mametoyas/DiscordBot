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
# Thai honorifics users stick in front of names ("เรียกไอ้Novaมาหน่อย")
THAI_PREFIX_RE = re.compile(r"^(ไอ้|อี|พี่|น้อง|คุณ|ท่าน|น้า|อา|ลุง|ป้า)\s*")


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
    candidates = [low]
    stripped = THAI_PREFIX_RE.sub("", name).strip().lower()
    if stripped and stripped != low:
        candidates.append(stripped)
    for cand in candidates:  # exact username or server nickname first (hijack-proof)
        for m in guild.members:
            if m.name.lower() == cand or m.display_name.lower() == cand:
                return m
    for cand in candidates:  # remembered custom nicknames ("ตั้งชื่อเล่นให้กัน")
        try:
            from src.utils.chat_store import store as _chat_store

            user_id = await _chat_store.get_alias(guild.id, cand)
        except Exception:  # noqa: BLE001 — alias lookup must never break search
            user_id = None
        if user_id:
            m = guild.get_member(int(user_id))
            if m:
                return m
            try:
                return await guild.fetch_member(int(user_id))
            except (discord.NotFound, discord.HTTPException, ValueError):
                pass
    try:  # server-side username search (needs Server Members Intent)
        found = await guild.query_members(query=name, limit=1)
        if found:
            return found[0]
    except (discord.HTTPException, AttributeError):
        pass
    for cand in candidates:
        for m in guild.members:
            if cand in m.display_name.lower() or cand in m.name.lower():
                return m
    return None


TEXT_KINDS = (
    discord.ChannelType.text,
    discord.ChannelType.news,
    discord.ChannelType.forum,
)
