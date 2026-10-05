"""Persistent chat memory (Supabase Postgres) with in-memory fallback.

Memory key: (channel_id, user_id) — each person gets their own history
inside each channel, so two people chatting in the same channel no longer
see each other's context mixed together.

Setup (one time, see SUPABASE_SETUP below):
  1. supabase.com -> New project (free), region Singapore.
  2. SQL Editor -> run the CREATE TABLE statement from SUPABASE_SETUP.
  3. Settings -> API -> copy Project URL + service_role key into .env:
       SUPABASE_URL=https://xyz.supabase.co
       SUPABASE_KEY=<service_role key, server-side only, never commit>

Behavior:
  - If SUPABASE_URL/KEY are missing OR Supabase errors -> silently falls
    back to the local in-memory deque (bot keeps working, memory just
    won't survive restart).
  - Retention: keeps the newest CHAT_KEEP_PAIRS pairs per user/channel;
    rows older than CHAT_RETENTION_DAYS are pruned opportunistically.
"""

import logging
import random
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import httpx

from src import config

log = logging.getLogger("gemini-bot")

TABLE = "chat_history"

SUPABASE_SETUP = """
create table if not exists chat_history (
  id bigint generated always as identity primary key,
  guild_id text,
  channel_id text not null,
  user_id text not null,
  role text not null check (role in ('user', 'model')),
  text text not null,
  created_at timestamptz default now()
);
create index if not exists chat_history_lookup
  on chat_history (channel_id, user_id, id desc);
"""

_local: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=config.HISTORY_LEN * 2))

_seeded_channels: set[str] = set()  # channels already backfilled this restart

ALIAS_SETUP = """
create table if not exists member_aliases (
  guild_id text not null,
  alias text not null,
  user_id text not null,
  set_by text,
  created_at timestamptz default now(),
  primary key (guild_id, alias)
);
"""

_alias_local: dict[tuple, str] = {}

MEMORIES_SETUP = """
create table if not exists memories (
  id bigint generated always as identity primary key,
  guild_id text not null,
  category text not null default 'general',
  key text not null,
  content text not null,
  created_by text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (guild_id, category, key)
);
create index if not exists memories_guild_lookup on memories (guild_id, updated_at desc);
"""

_memory_local: dict[tuple, dict] = {}


def _cfg(key: str, default: str = "") -> str:
    import os

    return os.getenv(key, default)


class ChatStore:
    def __init__(self):
        self.url = _cfg("SUPABASE_URL").rstrip("/")
        self.key = _cfg("SUPABASE_KEY")
        self.keep_pairs = int(_cfg("CHAT_KEEP_PAIRS", "20") or 20)
        self.retention_days = int(_cfg("CHAT_RETENTION_DAYS", "30") or 30)
        self._client: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.key)

    def _client_or_new(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    def _headers(self) -> dict:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def _local_get(self, channel_id, user_id=None) -> list[dict]:
        # Channel-shared pool: everyone in the channel sees the same history.
        return list(_local[(str(channel_id), "*")])

    def _local_add(self, channel_id, user_id, role: str, text: str):
        _local[(str(channel_id), "*")].append({"role": role, "text": text[:2000]})

    async def _fetch_all(self, channel_id, user_id=None, limit: int = 40) -> list[dict]:
        """Newest-last messages in this CHANNEL (all users share). Never raises."""
        if not self.enabled:
            return self._local_get(channel_id)[-limit:]
        try:
            c = self._client_or_new()
            r = await c.get(
                f"{self.url}/rest/v1/{TABLE}"
                f"?channel_id=eq.{channel_id}"
                f"&select=role,text&order=id.desc&limit={limit}",
                headers=self._headers(),
            )
            r.raise_for_status()
            return [{"role": row["role"], "text": row["text"]} for row in reversed(r.json())]
        except Exception as e:  # noqa: BLE001 — fallback must never break chat
            log.warning("[ChatStore] get failed, using local memory: %s", e)
            return self._local_get(channel_id)[-limit:]

    async def get(self, channel_id, user_id=None) -> list[dict]:
        """Newest-last list of {role, text}, capped at keep_pairs*2. Never raises."""
        return await self._fetch_all(channel_id, limit=self.keep_pairs * 2)

    async def get_with_summary(self, channel_id, user_id=None) -> tuple:
        """(summary|None, recent messages). Overflow older than the keep window
        is compressed into one summary (discord-agent style). Never raises."""
        import os as _os

        compress_at = int(_os.getenv("CHAT_COMPRESS_AT", "60") or 60)
        msgs = await self._fetch_all(channel_id, limit=compress_at)
        window = self.keep_pairs * 2
        if len(msgs) <= window:
            return None, msgs
        summary = await self._summarize(msgs[:-window])
        return summary, msgs[-window:]

    async def _summarize(self, messages: list[dict]) -> str | None:
        if not messages:
            return None
        try:
            from src.core import llm as _llm

            text = "\n".join(f"{m['role']}: {m['text'][:300]}" for m in messages)
            out = await _llm.generate_text(
                "Summarize this chat concisely: keep facts, preferences, decisions. "
                "Same language as the chat. Under 800 characters.\n" + text,
                temperature=0.0,
            )
            return (out or "").strip()[:1000] or None
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] summarize failed: %s", e)
            return None

    async def add(self, channel_id, user_id, role: str, text: str, guild_id=None):
        """Append one message locally AND remotely. Never raises."""
        self._local_add(channel_id, user_id, role, text)
        if not self.enabled:
            return
        try:
            c = self._client_or_new()
            r = await c.post(
                f"{self.url}/rest/v1/{TABLE}",
                headers={**self._headers(), "Prefer": "return=minimal"},
                json=[{
                    "guild_id": str(guild_id) if guild_id else None,
                    "channel_id": str(channel_id),
                    "user_id": str(user_id),
                    "role": role,
                    "text": text[:2000],
                }],
            )
            r.raise_for_status()
            if random.random() < 0.05:
                await self._prune(channel_id)
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] add failed (local copy kept): %s", e)

    async def _prune(self, channel_id):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        try:
            c = self._client_or_new()
            await c.delete(
                f"{self.url}/rest/v1/{TABLE}"
                f"?channel_id=eq.{channel_id}&created_at=lt.{cutoff}",
                headers=self._headers(),
            )
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] prune failed: %s", e)

    async def ensure_backfilled(self, channel_id, guild_id, discord_messages: list) -> int:
        """Seed the channel pool from real Discord history (oldest-first).

        discord_messages: iterable of objects with .author (bot/name/display_name),
        .content, .author.id. Skips empties/commands. Returns # seeded. Runs only
        when the pool is empty (tracked per restart + rechecked remotely).
        """
        if str(channel_id) in _seeded_channels:
            return 0
        _seeded_channels.add(str(channel_id))
        existing = await self._fetch_all(channel_id, limit=1)
        if existing:
            return 0
        count = 0
        for m in discord_messages:
            text = (m.content or "").strip()
            if not text or len(text) > 2000:
                continue
            if text.startswith(("/", "!", "@Bot")) and len(text) < 30:
                continue  # skip bare commands/pings, keep real talk
            author = m.author
            if getattr(author, "bot", False):
                role, label = "model", getattr(author, "display_name", "Bot")
            else:
                role = "user"
                label = getattr(author, "display_name", None) or getattr(author, "name", "?")
            await self.add(channel_id, getattr(author, "id", "?"), role,
                           f"{label}: {text}", guild_id)
            count += 1
        if count:
            log.info("[ChatStore] backfilled %d messages into channel %s", count, channel_id)
        return count

    # ---- member aliases: custom nicknames the bot remembers per server ----

    async def get_alias(self, guild_id, alias: str) -> str | None:
        """Return the remembered user_id for a nickname, or None. Never raises."""
        key = (str(guild_id), alias.strip().lower())
        if not self.enabled:
            return _alias_local.get(key)
        try:
            c = self._client_or_new()
            r = await c.get(
                f"{self.url}/rest/v1/member_aliases",
                headers=self._headers(),
                params={"guild_id": f"eq.{guild_id}", "alias": f"ilike.{alias.strip()}",
                        "select": "user_id", "limit": 1},
            )
            r.raise_for_status()
            rows = r.json()
            if rows:
                _alias_local[key] = rows[0]["user_id"]
                return rows[0]["user_id"]
            return _alias_local.get(key)
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] get_alias failed: %s", e)
            return _alias_local.get(key)

    async def set_alias(self, guild_id, alias: str, user_id, set_by=None):
        """Remember alias -> member for this server (upsert). Never raises."""
        alias = alias.strip()
        if not alias:
            raise ValueError("ชื่อเล่นว่างเปล่า")
        key = (str(guild_id), alias.lower())
        _alias_local[key] = str(user_id)
        if not self.enabled:
            return
        try:
            c = self._client_or_new()
            r = await c.post(
                f"{self.url}/rest/v1/member_aliases?on_conflict=guild_id,alias",
                headers={**self._headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=[{"guild_id": str(guild_id), "alias": alias,
                       "user_id": str(user_id), "set_by": str(set_by) if set_by else None}],
            )
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] set_alias failed (local copy kept): %s", e)

    async def remove_alias(self, guild_id, alias: str) -> bool:
        """Forget a nickname. Returns True if something was removed."""
        key = (str(guild_id), alias.strip().lower())
        had_local = _alias_local.pop(key, None) is not None
        if not self.enabled:
            return had_local
        try:
            c = self._client_or_new()
            r = await c.delete(
                f"{self.url}/rest/v1/member_aliases",
                headers=self._headers(),
                params={"guild_id": f"eq.{guild_id}", "alias": f"eq.{alias.strip()}"},
            )
            r.raise_for_status()
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] remove_alias failed: %s", e)
            return had_local

    async def list_aliases(self, guild_id) -> list[dict]:
        """All remembered nicknames for a server. Never raises."""
        if not self.enabled:
            return [{"alias": a, "user_id": u}
                    for (g, a), u in sorted(_alias_local.items()) if g == str(guild_id)]
        try:
            c = self._client_or_new()
            r = await c.get(
                f"{self.url}/rest/v1/member_aliases",
                headers=self._headers(),
                params={"guild_id": f"eq.{guild_id}", "select": "alias,user_id",
                        "order": "alias", "limit": 200},
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] list_aliases failed: %s", e)
            return [{"alias": a, "user_id": u}
                    for (g, a), u in sorted(_alias_local.items()) if g == str(guild_id)]


    async def aliases_for_member(self, guild_id, user_id) -> list[str]:
        """Nicknames remembered for ONE member. Never raises."""
        all_rows = await self.list_aliases(guild_id)
        return [r["alias"] for r in all_rows if str(r.get("user_id")) == str(user_id)]

    # ---- shared guild memories (remember/recall/forget, discord-agent style) ----

    @staticmethod
    def _tokens(query: str, limit: int = 6) -> list[str]:
        import re

        words = re.findall(r"[^\s,.!?;:()\"']+", str(query or ""))
        return [w for w in words if len(w) >= 2][:limit]

    async def remember_fact(self, guild_id, key: str, content: str,
                            category: str = "general", created_by=None):
        """Store/update one shared fact (upsert). Never raises (except empty key)."""
        key = (key or "").strip()
        if not key:
            raise ValueError("ต้องมีหัวข้อ (key) ที่จะจำ")
        category = (category or "general").strip() or "general"
        k = (str(guild_id), category.lower(), key.lower())
        _memory_local[k] = {"key": key, "content": content, "category": category}
        if not self.enabled:
            return
        try:
            from datetime import datetime as _dt, timezone as _tz

            c = self._client_or_new()
            r = await c.post(
                f"{self.url}/rest/v1/memories?on_conflict=guild_id,category,key",
                headers={**self._headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=[{"guild_id": str(guild_id), "category": category, "key": key,
                       "content": content, "created_by": str(created_by) if created_by else None,
                       "updated_at": _dt.now(_tz.utc).isoformat()}],
            )
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] remember_fact failed (local copy kept): %s", e)

    def _local_recall(self, guild_id, toks: list[str], limit: int) -> list[dict]:
        out = [v for (g, _c, _k), v in _memory_local.items() if g == str(guild_id)]
        if not toks:
            return out[-limit:]
        scored = [v for v in out
                  if any(t.lower() in (v["key"] + " " + v["content"]).lower() for t in toks)]
        return (scored or out)[-limit:]

    async def recall_matching(self, guild_id, query: str, limit: int = 5) -> list[dict]:
        """Facts whose key/content matches query words (ILIKE OR). Never raises.

        Fallbacks (in order): keyword match -> recent facts -> local copy.
        Small servers benefit: a miss still surfaces what was remembered lately.
        """
        toks = self._tokens(query)
        if not self.enabled:
            return self._local_recall(guild_id, toks, limit)
        try:
            c = self._client_or_new()
            base = {"guild_id": f"eq.{guild_id}", "select": "category,key,content",
                    "order": "updated_at.desc", "limit": limit}
            if toks:
                ors = ",".join(f"key.ilike.*{t}*,content.ilike.*{t}*" for t in toks)
                r = await c.get(f"{self.url}/rest/v1/memories", headers=self._headers(),
                                params={**base, "or": f"({ors})"})
                r.raise_for_status()
                rows = r.json()
                if rows:
                    return rows
            r = await c.get(f"{self.url}/rest/v1/memories",
                            headers=self._headers(), params=base)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] recall_matching failed, using local copy: %s", e)
            return self._local_recall(guild_id, toks, limit)

    async def forget_fact(self, guild_id, key: str, category: str = "general") -> bool:
        """Delete one shared fact. Returns True if something was removed."""
        category = (category or "general").strip() or "general"
        k = (str(guild_id), category.lower(), (key or "").strip().lower())
        had_local = _memory_local.pop(k, None) is not None
        if not self.enabled:
            return had_local
        try:
            c = self._client_or_new()
            r = await c.delete(
                f"{self.url}/rest/v1/memories", headers=self._headers(),
                params={"guild_id": f"eq.{guild_id}", "category": f"eq.{category}",
                        "key": f"eq.{key.strip()}"})
            r.raise_for_status()
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] forget_fact failed: %s", e)
            return had_local


store = ChatStore()