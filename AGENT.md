# AGENT.md — Instructions for AI Agents (READ FIRST)

> Entry point for any new AI agent continuing work on this repo.

## 1. What is this repo?

Discord AI bot (Python) using **hosted Gemini API** (no local LLM, no self-hosted server).
Runs as a **persistent worker on Render** (websocket gateway). Vercel is NOT supported for the current feature set — see `QA.md`.

## 2. Read order for a new agent

1. `README.md` — 1-min overview + quickstart
2. `PLAN.md` — where we are, what's next
3. `ARCHITECTURE.md` — how `bot.py` works (key rotation, reply triggers, history)
4. `QA.md` — past decisions (Render vs Vercel, raw REST vs SDK, etc.)
5. `TESTER.md` — how to verify changes
6. `DEPLOY.md` — how to ship to Render
7. `TODO.md` — actionable backlog

## 3. Repo map

| File | Purpose |
|---|---|
| `bot.py` | Thin entry (client + `/ask` + events; mirrors `discord-bot-agents/src/index.js`) |
| `src/config.py` | All env loading (mirrors `config.js`) |
| `src/core/llm.py` | `GeminiRotator` (multi-key) + `generate_text()`; JSON via `utils/json_helper` |
| `src/agent/` | `run()` = prefetch → planner → executor → summarizer + `language.py` + `composer.py` (mirrors `src/agent/`) |
| `src/skills/` | 34 Discord skills in 7 modules + registry (mirrors `src/skills/`) |
| `src/handler/message_handler.py` | Mention/cooldown/greeting + agent/chat routing (mirrors `src/handler/`) |
| `src/utils/` | `fuzzy_match` / `error_mapper` / `json_helper` / `snipe_manager` (mirrors `src/utils/`) |
| `discord-bot-agents/` | Reference Node.js implementation (read-only, do not edit) |
| `requirements.txt` | `discord.py`, `httpx`, `python-dotenv` |
| `Procfile` | `worker: python bot.py` |
| `render.yaml` | Render Blueprint (worker service) |
| `.env.example` | Required env vars template (never commit real `.env`) |
| `.gitignore` | Excludes `.env`, `__pycache__` |

## 4. Rules

- **Never commit secrets.** `.env` is gitignored. Use `.env.example` as template.
- **Prefer editing `bot.py` over new files.** Keep the bot single-file until >500 lines.
- **No new `.md` docs unless user asks.** Update existing ones instead.
- **Verify before claiming done:** `py -3 -m py_compile bot.py` (note: this dev machine has NO Python — see `TESTER.md`), plus Discord manual test checklist.
- **Env var names are contract:** `DISCORD_TOKEN`, `GEMINI_KEYS` (comma-separated), `GEMINI_MODEL`, `AUTO_REPLY_CHANNEL_IDS`, `HISTORY_LEN`, `SYSTEM_PROMPT`. Changing a name requires updating `.env.example` + `render.yaml` + `DEPLOY.md` together.
- **Language:** reply to user in Thai; code comments/logging in Thai+English mix is OK (existing style).

## 5. Key facts (don't re-discover)

- Layout mirrors `discord-bot-agents/src/`: `src/agent|config|core|handler|skills|utils`. `bot.py` is a thin entry (`python bot.py` keeps Procfile/render.yaml working).
- LLM lives in **`src/core/llm.py`**: raw REST via `httpx`, multi-key rotation + 60s cooldown on 429/403/500/503. JSON parsing lives in **`src/utils/json_helper.py`** (fences, trailing commas, smart quotes, loose-field fallback).
- Agent loop: `src/agent/__init__.py:run()` = prefetch (trigger keywords → `skill.fetch_raw`, no LLM) → plan (temp 0, ≤5 actions, deduped, language instruction) → execute (perm + role-hierarchy guards, `error_mapper`) → summarize → `composer`.
- Reply routing (`src/handler/message_handler.py`): **guild mention → agent**; empty mention → greeting (0 LLM); **DM / auto-channel / `/ask` → chat**. 2s per-user agent cooldown. Mention detection via `config.BOT_PREFIX` + `client.user in mentions`.
- Skills: `src.skills.SKILLS` registry; `required_permissions` use discord.py names; `targets_member=True` triggers hierarchy guard in executor. Entity lookup (`utils/fuzzy_match.py`) accepts mentions, `#id`/`@id`, raw IDs, exact/fuzzy names + API fetch fallback.
- History and snipes are in-memory (lost on restart, by design).
- Reference impl `discord-bot-agents/` is **read-only**; reusable Agent Skill lives at `~/.agents/skills/discord-bot-agent/`.

## 6. How to continue a task

1. Check `TODO.md` + `PLAN.md` § "Next" for the current goal.
2. Make the smallest edit that satisfies it.
3. Update `PLAN.md` (status) + `CHANGELOG.md` (what changed) in the same turn.
4. Tell the user how to verify (Discord test steps from `TESTER.md`).
