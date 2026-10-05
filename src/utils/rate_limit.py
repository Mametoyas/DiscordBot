"""Per-user / per-guild rate limiting (ENHANCE.md Phase 4: cost-abuse fix).

Token-bucket style with monotonic clocks. Synchronous + dependency-free so both
the Discord handler (async) and tests can use it without I/O.

Defaults (env-overridable in config.py) target a single small free-tier guild:
  chat:  1 msg / CHAT_COOLDOWN_SEC per user, max CHAT_BURST_PER_MIN per user/min
  agent: config.AGENT_COOLDOWN_SEC already exists; this adds a per-minute cap
  guild: global cap so one server can't burn the whole Gemini RPD quota
"""

import time


class Bucket:
    """Sliding-window counter: allow() returns True if under limit."""

    def __init__(self, max_hits: int, window_sec: float):
        self.max_hits = max(1, max_hits)
        self.window = max(1.0, window_sec)
        self._hits: dict[int | str, list[float]] = {}

    def _prune(self, key, now: float) -> list[float]:
        hits = self._hits.get(key, [])
        cutoff = now - self.window
        hits = [t for t in hits if t > cutoff]
        self._hits[key] = hits
        return hits

    def allow(self, key, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = self._prune(key, now)
        if len(hits) >= self.max_hits:
            return False
        hits.append(now)
        return True

    def retry_after(self, key, now: float | None = None) -> float:
        now = time.monotonic() if now is None else now
        hits = self._prune(key, now)
        if len(hits) < self.max_hits:
            return 0.0
        return max(0.0, hits[0] + self.window - now)


class RateLimiter:
    """Combined chat/agent/guild limiter with friendly Thai deny messages."""

    def __init__(self, chat_per_min: int = 6, agent_per_min: int = 10,
                 guild_per_min: int = 40, chat_cooldown_sec: float = 5.0):
        self.chat = Bucket(chat_per_min, 60.0)
        self.agent = Bucket(agent_per_min, 60.0)
        self.guild = Bucket(guild_per_min, 60.0)
        self.chat_cooldown_sec = chat_cooldown_sec
        self._last_chat: dict[int, float] = {}

    def check_chat(self, user_id: int, guild_id=None,
                   now: float | None = None) -> tuple[bool, str]:
        """Returns (allowed, reason). reason is '' when allowed."""
        now = time.monotonic() if now is None else now
        last = self._last_chat.get(user_id, 0.0)
        if now - last < self.chat_cooldown_sec:
            return False, "cooldown"
        if not self.chat.allow(user_id, now):
            return False, "user-quota"
        if guild_id is not None and not self.guild.allow(f"g{guild_id}", now):
            return False, "guild-quota"
        self._last_chat[user_id] = now
        return True, ""

    def check_agent(self, user_id: int, guild_id=None,
                    now: float | None = None) -> tuple[bool, str]:
        now = time.monotonic() if now is None else now
        if not self.agent.allow(user_id, now):
            return False, "user-quota"
        if guild_id is not None and not self.guild.allow(f"g{guild_id}", now):
            return False, "guild-quota"
        return True, ""


# Shared instance used by the handler; tests construct their own.
limiter = RateLimiter()

DENY_MSG = "⏳ ช้าหน่อยนะ ส่งถี่ไปแล้ว (พัก {sec}s แล้วลองใหม่)"
QUOTA_MSG = ("🔋 โควต้า AI หมดชั่วคราว (free-tier) — "
             "พักสักครู่แล้วลองใหม่นะ ไม่ได้เสีย แค่ให้ Gemini หายใจก่อน")
