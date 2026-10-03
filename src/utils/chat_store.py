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

    def _local_get(self, channel_id, user_id) -> list[dict]:
        return list(_local[(str(channel_id), str(user_id))])

    def _local_add(self, channel_id, user_id, role: str, text: str):
        _local[(str(channel_id), str(user_id))].append({"role": role, "text": text[:2000]})

    async def get(self, channel_id, user_id) -> list[dict]:
        """Newest-last list of {role, text}, capped at keep_pairs*2. Never raises."""
        if not self.enabled:
            return self._local_get(channel_id, user_id)
        try:
            c = self._client_or_new()
            r = await c.get(
                f"{self.url}/rest/v1/{TABLE}"
                f"?channel_id=eq.{channel_id}&user_id=eq.{user_id}"
                f"&select=role,text&order=id.desc&limit={self.keep_pairs * 2}",
                headers=self._headers(),
            )
            r.raise_for_status()
            return [{"role": row["role"], "text": row["text"]} for row in reversed(r.json())]
        except Exception as e:  # noqa: BLE001 — fallback must never break chat
            log.warning("[ChatStore] get failed, using local memory: %s", e)
            return self._local_get(channel_id, user_id)

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
                await self._prune(channel_id, user_id)
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] add failed (local copy kept): %s", e)

    async def _prune(self, channel_id, user_id):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        try:
            c = self._client_or_new()
            await c.delete(
                f"{self.url}/rest/v1/{TABLE}"
                f"?channel_id=eq.{channel_id}&user_id=eq.{user_id}&created_at=lt.{cutoff}",
                headers=self._headers(),
            )
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] prune failed: %s", e)

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
                params={"guild_id": f"eq.{guild_id}", "alias": f"eq.{alias.strip()}",
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


store = ChatStore()
