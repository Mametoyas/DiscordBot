"""Auto-create Supabase tables on boot (idempotent).

PostgREST can't run DDL, so this uses a direct Postgres connection via asyncpg.
Opt-in: runs ONLY when SUPABASE_DB_URL is set (copy from Supabase dashboard ->
Connect -> Connection string, pooler mode recommended). Never crashes boot.

Covers: chat_history, member_aliases, memories (+ indexes, RLS + permissive
policies matching the manual guide, for publishable/anon keys; service_role
bypasses RLS anyway).
"""

import logging
import re

log = logging.getLogger("gemini-bot")

_BOOTSTRAPPED = False


def split_statements(script: str) -> list[str]:
    """Split SQL on semicolons, ignoring those inside dollar-quoted (DO $$) blocks."""
    stmts, buf, i, tag = [], [], 0, None
    while i < len(script):
        if tag is None:
            m = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", script[i:])
            if m:
                tag = m.group(0)
                buf.append(tag)
                i += len(tag)
                continue
            if script[i] == ";":
                stmt = "".join(buf).strip()
                if stmt:
                    stmts.append(stmt)
                buf = []
                i += 1
                continue
            buf.append(script[i])
            i += 1
        else:
            if script.startswith(tag, i):
                buf.append(tag)
                i += len(tag)
                tag = None
                continue
            buf.append(script[i])
            i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def _schema_sql() -> str:
    from src.utils.chat_store import SUPABASE_SETUP, ALIAS_SETUP, MEMORIES_SETUP

    return "\n".join([
        SUPABASE_SETUP,
        ALIAS_SETUP,
        MEMORIES_SETUP,
        """
        alter table if exists chat_history enable row level security;
        alter table if exists member_aliases enable row level security;
        alter table if exists memories enable row level security;
        """,
        """
        do $$ begin
          if not exists (select 1 from pg_policies
                         where tablename = 'chat_history' and policyname = 'bot full access') then
            create policy "bot full access" on chat_history
              for all using (true) with check (true);
          end if;
          if not exists (select 1 from pg_policies
                         where tablename = 'member_aliases' and policyname = 'bot full access') then
            create policy "bot full access" on member_aliases
              for all using (true) with check (true);
          end if;
          if not exists (select 1 from pg_policies
                         where tablename = 'memories' and policyname = 'bot full access') then
            create policy "bot full access" on memories
              for all using (true) with check (true);
          end if;
        end $$;
        """,
    ])


async def ensure_tables() -> bool:
    """Create missing tables/policies. Returns True if attempted ok, False if skipped/failed."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return True
    _BOOTSTRAPPED = True

    import os
    dsn = os.getenv("SUPABASE_DB_URL", "").strip()
    if not dsn:
        log.info("[DB] SUPABASE_DB_URL not set — skipping auto-create (tables must exist)")
        return False
    try:
        import asyncpg
    except ImportError:
        log.warning("[DB] asyncpg not installed — skipping auto-create (pip install asyncpg)")
        return False
    try:
        # statement_cache_size=0: prepared statements break under pooler
        # Transaction mode, so disable them (works in Session mode too).
        conn = await asyncpg.connect(dsn, timeout=15, statement_cache_size=0)
        try:
            for stmt in split_statements(_schema_sql()):
                await conn.execute(stmt)
        finally:
            await conn.close()
        log.info("[DB] tables ensured (chat_history, member_aliases, memories)")
        return True
    except Exception as e:  # noqa: BLE001 — never crash boot
        log.warning("[DB] auto-create failed (bot still runs): %s", str(e)[:300])
        return False
