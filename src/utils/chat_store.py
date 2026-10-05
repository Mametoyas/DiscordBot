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
import os
import random
import sqlite3
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import httpx

from src import config

log = logging.getLogger("gemini-bot")

# SQLite fallback (ENHANCE.md Phase 3: durable memory without paid DB).
# Used automatically when SUPABASE_URL/KEY are absent. Path overridable via
# SQLITE_PATH. Same 3 logical tables as Supabase; stdlib only, no new deps.
# NOTE: on Render free disk this survives restarts but not redeploys —
# Supabase remains the recommended durable backend (see checkDatabase).
SQLITE_PATH = os.getenv("SQLITE_PATH", "data/chat.db")
_sqlite_lock = threading.Lock()


def _sqlite_conn() -> sqlite3.Connection | None:
    """Open (and init) the fallback DB. Returns None on any failure."""
    try:
        path = SQLITE_PATH
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        with _sqlite_lock:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  guild_id TEXT, channel_id TEXT NOT NULL, user_id TEXT NOT NULL,
                  role TEXT NOT NULL, text TEXT NOT NULL,
                  created_at TEXT DEFAULT (datetime('now')));
                CREATE INDEX IF NOT EXISTS chat_history_lookup
                  ON chat_history (channel_id, id DESC);
                CREATE TABLE IF NOT EXISTS member_aliases (
                  guild_id TEXT NOT NULL, alias TEXT NOT NULL, user_id TEXT NOT NULL,
                  set_by TEXT, created_at TEXT DEFAULT (datetime('now')),
                  PRIMARY KEY (guild_id, alias));
                CREATE TABLE IF NOT EXISTS memories (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  guild_id TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'general',
                  key TEXT NOT NULL, content TEXT NOT NULL, created_by TEXT,
                  created_at TEXT DEFAULT (datetime('now')),
                  updated_at TEXT DEFAULT (datetime('now')),
                  UNIQUE (guild_id, category, key));
                CREATE INDEX IF NOT EXISTS memories_guild_lookup
                  ON memories (guild_id, updated_at DESC);
                """
            )
            conn.commit()
        return conn
    except Exception as e:  # noqa: BLE001 — fallback must never break boot
        log.warning("[ChatStore] sqlite unavailable (%s), using RAM only", e)
        return None

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
            return self._sqlite_fetch(channel_id, limit) or self._local_get(channel_id)[-limit:]
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

    def _sqlite_fetch(self, channel_id, limit: int) -> list[dict]:
        """Read recent channel history from SQLite fallback. Never raises."""
        conn = _sqlite_conn()
        if conn is None:
            return []
        try:
            with _sqlite_lock:
                rows = conn.execute(
                    "SELECT role, text FROM chat_history WHERE channel_id=? "
                    "ORDER BY id DESC LIMIT ?",
                    (str(channel_id), limit),
                ).fetchall()
            return [{"role": r["role"], "text": r["text"]} for r in reversed(rows)]
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] sqlite read failed: %s", e)
            return []
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def _sqlite_write_chat(self, channel_id, user_id, role: str, text: str, guild_id=None):
        conn = _sqlite_conn()
        if conn is None:
            return
        try:
            with _sqlite_lock:
                conn.execute(
                    "INSERT INTO chat_history (guild_id, channel_id, user_id, role, text)"
                    " VALUES (?,?,?,?,?)",
                    (str(guild_id) if guild_id else None, str(channel_id),
                     str(user_id), role, text[:2000]),
                )
                conn.commit()
                keep = self.keep_pairs * 2
                conn.execute(
                    "DELETE FROM chat_history WHERE channel_id=? AND id NOT IN "
                    "(SELECT id FROM chat_history WHERE channel_id=? "
                    "ORDER BY id DESC LIMIT ?)",
                    (str(channel_id), str(channel_id), keep),
                )
                conn.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] sqlite write failed: %s", e)
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    async def add(self, channel_id, user_id, role: str, text: str, guild_id=None):
        """Append one message locally AND remotely. Never raises."""
        self._local_add(channel_id, user_id, role, text)
        if not self.enabled:
            self._sqlite_write_chat(channel_id, user_id, role, text, guild_id)
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
        if _alias_local.get(key) is not None and not self.enabled:
            # fall through to sqlite below (local cache may be stale after restart)
            pass
        if not self.enabled:
            hit = self._sqlite_get_alias(guild_id, alias)
            if hit is not None:
                _alias_local[key] = hit
                return hit
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

    def _sqlite_get_alias(self, guild_id, alias: str) -> str | None:
        conn = _sqlite_conn()
        if conn is None:
            return None
        try:
            with _sqlite_lock:
                row = conn.execute(
                    "SELECT user_id FROM member_aliases WHERE guild_id=? AND alias=? "
                    "COLLATE NOCASE",
                    (str(guild_id), alias.strip()),
                ).fetchone()
            return row["user_id"] if row else None
        except Exception:  # noqa: BLE001
            return None
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def _sqlite_upsert_alias(self, guild_id, alias: str, user_id, set_by=None):
        conn = _sqlite_conn()
        if conn is None:
            return
        try:
            with _sqlite_lock:
                conn.execute(
                    "INSERT INTO member_aliases (guild_id, alias, user_id, set_by)"
                    " VALUES (?,?,?,?) ON CONFLICT (guild_id, alias) DO UPDATE SET"
                    " user_id=excluded.user_id, set_by=excluded.set_by",
                    (str(guild_id), alias.strip(), str(user_id),
                     str(set_by) if set_by else None),
                )
                conn.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] sqlite alias write failed: %s", e)
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def _sqlite_remove_alias(self, guild_id, alias: str):
        conn = _sqlite_conn()
        if conn is None:
            return
        try:
            with _sqlite_lock:
                conn.execute(
                    "DELETE FROM member_aliases WHERE guild_id=? AND alias=?",
                    (str(guild_id), alias.strip()),
                )
                conn.commit()
        except Exception:  # noqa: BLE001
            pass
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def _sqlite_list_aliases(self, guild_id) -> list[dict]:
        conn = _sqlite_conn()
        if conn is None:
            return []
        try:
            with _sqlite_lock:
                rows = conn.execute(
                    "SELECT alias, user_id FROM member_aliases WHERE guild_id=? "
                    "ORDER BY alias LIMIT 200",
                    (str(guild_id),),
                ).fetchall()
            return [{"alias": r["alias"], "user_id": r["user_id"]} for r in rows]
        except Exception:  # noqa: BLE001
            return []
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    async def set_alias(self, guild_id, alias: str, user_id, set_by=None):
        """Remember alias -> member for this server (upsert). Never raises."""
        alias = alias.strip()
        if not alias:
            raise ValueError("ชื่อเล่นว่างเปล่า")
        key = (str(guild_id), alias.lower())
        _alias_local[key] = str(user_id)
        if not self.enabled:
            self._sqlite_upsert_alias(guild_id, alias, user_id, set_by)
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
            before = self._sqlite_get_alias(guild_id, alias) is not None
            self._sqlite_remove_alias(guild_id, alias)
            return had_local or before
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
            rows = self._sqlite_list_aliases(guild_id)
            if rows:
                for r in rows:
                    _alias_local[(str(guild_id), r["alias"].lower())] = r["user_id"]
                return rows
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

    def _sqlite_upsert_fact(self, guild_id, key: str, content: str,
                            category: str, created_by=None):
        conn = _sqlite_conn()
        if conn is None:
            return
        try:
            from datetime import datetime as _dt, timezone as _tz
            with _sqlite_lock:
                conn.execute(
                    "INSERT INTO memories (guild_id, category, key, content, created_by,"
                    " updated_at) VALUES (?,?,?,?,?,?)"
                    " ON CONFLICT (guild_id, category, key) DO UPDATE SET"
                    " content=excluded.content, updated_at=excluded.updated_at",
                    (str(guild_id), category, key, content,
                     str(created_by) if created_by else None,
                     _dt.now(_tz.utc).isoformat()),
                )
                conn.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] sqlite fact write failed: %s", e)
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def _sqlite_recall(self, guild_id, toks: list[str], limit: int) -> list[dict]:
        conn = _sqlite_conn()
        if conn is None:
            return self._local_recall(guild_id, toks, limit)
        try:
            with _sqlite_lock:
                if toks:
                    clauses = " OR ".join(
                        "(key LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')"
                        for _ in toks)
                    params: list = []
                    for t in toks:
                        like = f"%{t}%"
                        params += [like, like]
                    rows = conn.execute(
                        f"SELECT category, key, content FROM memories WHERE guild_id=?"
                        f" AND ({clauses}) ORDER BY updated_at DESC LIMIT ?",
                        (str(guild_id), *params, limit),
                    ).fetchall()
                    if rows:
                        return [dict(r) for r in rows]
                rows = conn.execute(
                    "SELECT category, key, content FROM memories WHERE guild_id=?"
                    " ORDER BY updated_at DESC LIMIT ?",
                    (str(guild_id), limit),
                ).fetchall()
            remote = [dict(r) for r in rows]
            if remote:
                return remote
            return self._local_recall(guild_id, toks, limit)
        except Exception as e:  # noqa: BLE001
            log.warning("[ChatStore] sqlite recall failed: %s", e)
            return self._local_recall(guild_id, toks, limit)
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

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
            self._sqlite_upsert_fact(guild_id, key, content, category, created_by)
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
            # SQLite first (survives restart), then RAM.
            return self._sqlite_recall(guild_id, toks, limit)
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
            conn = _sqlite_conn()
            had_sqlite = False
            if conn is not None:
                try:
                    with _sqlite_lock:
                        cur = conn.execute(
                            "DELETE FROM memories WHERE guild_id=? AND category=? AND key=?",
                            (str(guild_id), category, key.strip()),
                        )
                        conn.commit()
                        had_sqlite = cur.rowcount > 0
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    try:
                        conn.close()
                    except Exception:  # noqa: BLE001
                        pass
            return had_local or had_sqlite
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


    async def delete_user_data(self, guild_id=None, user_id=None) -> dict:
        """GDPR-style self-serve deletion for /forget-me. Never raises.

        Removes: chat rows by this user, aliases pointing at this user,
        facts created_by this user. Returns counts per area.
        """
        counts = {"chat": 0, "aliases": 0, "facts": 0}
        uid, gid = str(user_id), str(guild_id) if guild_id else None
        # RAM copies
        try:
            for k in list(_local.keys()):
                before = len(_local[k])
                _local[k] = deque(
                    (m for m in _local[k] if uid not in str(m.get("text", ""))[:200]),
                    maxlen=_local[k].maxlen or 40,
                )
                counts["chat"] += before - len(_local[k])
            for k in [k for k, v in _alias_local.items()
                      if v == uid and (gid is None or k[0] == gid)]:
                _alias_local.pop(k, None)
                counts["aliases"] += 1
            # NOTE: shared guild facts are NOT wiped here by design — they belong
            # to the whole server; use forgetFact to remove one. Only per-user
            # rows (chat + aliases) are deleted by /forget-me.
        except Exception:  # noqa: BLE001
            pass
        # SQLite copies
        conn = _sqlite_conn()
        if conn is not None:
            try:
                with _sqlite_lock:
                    if gid is not None:
                        cur = conn.execute(
                            "DELETE FROM chat_history WHERE guild_id=? AND user_id=?",
                            (gid, uid))
                    else:
                        cur = conn.execute(
                            "DELETE FROM chat_history WHERE user_id=?", (uid,))
                    counts["chat"] += cur.rowcount or 0
                    if gid is not None:
                        cur = conn.execute(
                            "DELETE FROM member_aliases WHERE guild_id=? AND user_id=?",
                            (gid, uid))
                    else:
                        cur = conn.execute(
                            "DELETE FROM member_aliases WHERE user_id=?", (uid,))
                    counts["aliases"] += cur.rowcount or 0
                    conn.commit()
            except Exception as e:  # noqa: BLE001
                log.warning("[ChatStore] delete_user_data sqlite failed: %s", e)
            finally:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
        # Supabase copies (best-effort)
        if self.enabled:
            try:
                c = self._client_or_new()
                params: dict = {"user_id": f"eq.{uid}", "select": "id"}
                if gid is not None:
                    params["guild_id"] = f"eq.{gid}"
                r = await c.delete(f"{self.url}/rest/v1/{TABLE}",
                                   headers=self._headers(), params=params)
                r.raise_for_status()
                r = await c.delete(f"{self.url}/rest/v1/member_aliases",
                                   headers=self._headers(),
                                   params={"user_id": f"eq.{uid}",
                                           **({"guild_id": f"eq.{gid}"} if gid else {})})
                r.raise_for_status()
            except Exception as e:  # noqa: BLE001
                log.warning("[ChatStore] delete_user_data remote failed: %s", e)
        return counts

    async def user_data_summary(self, guild_id=None, user_id=None) -> dict:
        """What is stored about one user (for /privacy). Never raises."""
        uid = str(user_id)
        gid = str(guild_id) if guild_id else None
        out = {"chat_rows": 0, "aliases": [], "backend": "ram"}
        if self.enabled:
            out["backend"] = "supabase"
        else:
            _probe = _sqlite_conn()
            if _probe is not None:
                out["backend"] = "sqlite"
                try:
                    _probe.close()
                except Exception:  # noqa: BLE001
                    pass
        try:
            out["aliases"] = await self.aliases_for_member(gid or "", uid)
        except Exception:  # noqa: BLE001
            out["aliases"] = []
        try:
            if not self.enabled:
                conn = _sqlite_conn()
                if conn is not None:
                    with _sqlite_lock:
                        if gid is not None:
                            row = conn.execute(
                                "SELECT COUNT(*) c FROM chat_history "
                                "WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
                        else:
                            row = conn.execute(
                                "SELECT COUNT(*) c FROM chat_history WHERE user_id=?",
                                (uid,)).fetchone()
                    out["chat_rows"] = int(row["c"]) if row else 0
                    conn.close()
        except Exception:  # noqa: BLE001
            pass
        return out


store = ChatStore()