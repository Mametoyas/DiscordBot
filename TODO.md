# TODO.md — Backlog (highest value first)

- [ ] **P1 — Live verification**: run `TESTER.md` checklist C with real tokens (chat + agent skills); record results in `CHANGELOG.md`.
- [ ] **P1 — `tests/test_rotator.py` + `tests/test_agent.py`**: mock `httpx` (429→rotates, 200→text) and planner JSON (multi-intent→2 actions, mixed scope→[]). Unblocks CI.
- [ ] **P2 — Per-user cooldown in auto/DM chat**: agent path already has 2s cooldown (`bot.py`); extend to chat path (spam guard).
- [ ] **P2 — Graceful quota message**: when all keys dead, reply Thai-friendly "โควต้าหมด ช้าลงหน่อย" instead of raw exception.
- [ ] **P2 — Token/key usage log**: log which key index served each request (already partially via `mark_dead`; add success log).
- [ ] **P2 — `Dockerfile`** (python:3.11-slim, `CMD ["python","bot.py"]`) for Fly.io / local docker alternative.
- [ ] **P3 — Per-user history**: switch `_histories` key to `(channel_id, user_id)` or thread-based.
- [ ] **P3 — Vercel slash-only variant**: separate `api/interactions.py` (verify Ed25519 + call Gemini) — only if user still wants Vercel.
- [ ] **P3 — Render health endpoint**: tiny `aiohttp` ping server so UptimeRobot can keep free worker awake.

> Agent: when you finish an item, check it off here + add a `CHANGELOG.md` entry in the same turn.
