"""Auto-create Supabase tables on boot (idempotent).

PostgREST can't run DDL, so this uses a direct Postgres connection via asyncpg.
Opt-in: runs ONLY when SUPABASE_DB_URL is set (copy from Supabase dashboard ->
Connect -> Connection string, pooler mode recommended). Never crashes boot.

Covers: chat_history, member_aliases, memories (+ indexes, RLS + permissive
policies matching the manual guide, for publishable/anon keys; service_role
bypasses RLS anyway).
"""

import logging

log = logging.getLogger("gemini-bot")

_BOOTSTRAPPED = False


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
        conn = await asyncpg.connect(dsn, timeout=15)
        try:
            await conn.execute(_schema_sql())
        finally:
            await conn.close()
        log.info("[DB] tables ensured (chat_history, member_aliases, memories)")
        return True
    except Exception as e:  # noqa: BLE001 — never crash boot
        log.warning("[DB] auto-create failed (bot still runs): %s", str(e)[:300])
        return False
