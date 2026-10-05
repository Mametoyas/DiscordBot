# TODO.md — Backlog (highest value first)

- [ ] **P1 — Live verification**: run `TESTER.md` checklist C with real tokens (chat + agent skills); record results in `CHANGELOG.md`.
- [ ] **P1 — `tests/test_rotator.py` + `tests/test_agent.py`**: mock `httpx` (429→rotates, 200→text) and planner JSON (multi-intent→2 actions, mixed scope→[]). Unblocks CI.
- [x] **P2 — Per-user cooldown in auto/DM chat**: `src/utils/rate_limit.py` + handler integration (5s cooldown + 6/min/user, 40/min/guild).
- [x] **P2 — Graceful quota message**: `QUOTA_EXHAUSTED_MSG` (Thai) in `src/core/llm.py` instead of raw exception.
- [ ] **P2 — Token/key usage log**: log which key index served each request (already partially via `mark_dead`; add success log).
- [ ] **P2 — `Dockerfile`** (python:3.11-slim, `CMD ["python","bot.py"]`) for Fly.io / local docker alternative.
- [ ] **P3 — Per-user history**: switch `_histories` key to `(channel_id, user_id)` or thread-based.
- [ ] **P3 — Vercel slash-only variant**: separate `api/interactions.py` (verify Ed25519 + call Gemini) — only if user still wants Vercel.
- [ ] **P3 — Render health endpoint**: tiny `aiohttp` ping server so UptimeRobot can keep free worker awake.

> Agent: when you finish an item, check it off here + add a `CHANGELOG.md` entry in the same turn.
