# PLAN.md — Project Plan & Status

## Goal
Discord AI bot that uses hosted Gemini LLM, no self-hosted server, always-on in the cloud.
User requirements:
1. **Gemini multi-key rotation** — switch API key automatically on rate limit.
2. **Host on Render** (Vercel requested but rejected for gateway features — see QA.md).
3. **Three reply modes:** mention-reply, slash `/ask`, auto-reply to every message in bot's own channel.
4. **NEW: server-management agent like `discord-bot-agents`** — `@Bot` mention runs plan→execute→summarize with 34 Discord skills + reusable Agent Skill (`SKILL.md`).

## Current state (2026-09-29)

| Phase | Status | Notes |
|---|---|---|
| P0 — Core bot (`bot.py`, intents, `/ask`, mention reply) | ✅ Done | now thin entry, logic in `src/` |
| P0 — Gemini rotation (`GeminiRotator`) | ✅ Done | `src/core/llm.py`, comma-separated `GEMINI_KEYS` |
| P0 — Auto-reply channel (`AUTO_REPLY_CHANNEL_IDS`) + DM | ✅ Done | `src/config.py` + `src/handler/message_handler.py` |
| P0 — Render deploy config (`Procfile`, `render.yaml`, `requirements.txt`) | ✅ Done | Worker type, Python 3.11.9 |
| P1 — Real-token verification (Discord + Gemini live test) | ⬜ Not started | Blocked: needs user tokens + machine with Python |
| P1 — Handover docs (AGENT/PLAN/ARCH/QA/TESTER/DEPLOY/TODO/README/CHANGELOG) | ✅ Done | |
| P1 — Agent Skill `discord-bot-agent` (`~/.agents/skills/`, validated ✅) | ✅ Done | SKILL.md + skill-catalog/agent-prompts/scope-rules refs |
| P1 — Python port: `src/` mirror (34 skills + agent) wired into mentions | ✅ Done (code, unverified live) | Guild mention → agent; DM/auto-channel → chat; `/ask` → chat |
| P1 — Real-token verification (Discord + Gemini live test, incl. agent skills) | ⬜ Not started | Blocked: needs user tokens + machine with Python |
| P2 — Hardening (rate-limit per user, long-reply split, error UX) | ✅ Done 2026-10-05 | ENHANCE.md pass: constitution, rate_limit, quota msg, /privacy//forget-me |
| P2 — Persistence (history survives restart, e.g. Redis) | ✅ Partial 2026-10-05 | SQLite fallback added (Supabase still recommended for durable/multi-instance) |
| P3 — Serverless `/ask`-only variant for Vercel (optional) | ⬜ Backlog | Only if user still wants Vercel |

## Next (for the next agent)

1. **Live verification** — ask user for: (a) machine with Python 3.11+, (b) `DISCORD_TOKEN` + 2 Gemini keys, (c) test guild channel ID. Then follow `TESTER.md` (now includes agent skill checks).
2. **Deploy to Render** — follow `DEPLOY.md`, confirm `/ask` appears in Discord.
3. **Pick next hardening item from `TODO.md`** (suggested order: `tests/test_rotator.py` → per-user cooldown in auto channels → token usage log).

## Milestones

- [x] M1: Bot replies to mention + `/ask` + auto-channel locally (code complete, unverified live)
- [x] M1b: `@Bot` mention runs agent (34 skills) in guilds; Agent Skill validated
- [ ] M2: Deployed on Render, stays online 24h, key rotation observed in logs
- [ ] M3: Hardening v1 (spam guard + graceful quota-exhausted message)

## Out of scope (unless user asks)

- Voice / image generation, RAG, database, dashboard.
- Vercel full-bot support (technically impossible for gateway — only slash-via-webhook variant possible).
