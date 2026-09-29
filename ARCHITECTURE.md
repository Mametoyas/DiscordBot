# ARCHITECTURE.md — How the Bot Works

## Big picture

```
@Bot <request> in guild ──▶ agent/run() ──▶ plan (LLM) ──▶ execute (34 skills) ──▶ summarize (LLM) ──▶ reply
DM / auto-channel / /ask ──▶ chat (Gemini + per-channel history) ──▶ reply
```

Single process. Layout mirrors `discord-bot-agents/src/`: `bot.py` is the thin entry (like `index.js`), logic in `src/agent|config|core|handler|skills|utils`. `Procfile`/`render.yaml` still run `python bot.py`.

## Components

### 1. Config (`src/config.py`, mirrors `config.js`)
- `DISCORD_TOKEN`, `GEMINI_KEYS` (comma-split, plus legacy `GEMINI_KEY` fallback), `GEMINI_MODEL` (default `gemini-2.0-flash`).
- `AUTO_REPLY_CHANNEL_IDS`: set of channel-ID strings. Empty = only mention + DM reply.
- `HISTORY_LEN` (default 10 turns), `SYSTEM_PROMPT` (overridable via env).
- `load_dotenv()` for local dev; on Render values come from dashboard env vars.

### 2. `src/core/llm.py` — GeminiRotator + singleton
- `bot.py` calls `llm.configure()` once; everyone else uses `llm.generate_text()` / `get_client()` (no import cycles).
- Round-robin + 60s cooldown on 429/403/500/503; `system`/`temperature`/`max_tokens` overridable per call (planner uses temp 0).
- JSON parsing lives in `src/utils/json_helper.py` (fences, trailing-comma/smart-quote/control-char repairs, loose-field fallback); re-exported as `llm.extract_json`.

### 3. Agent loop (`src/agent/`, ~2 LLM calls per `@Bot` command)
- `__init__.py:run()` = `prefetch` (trigger keywords → `skill.fetch_raw` on info/list skills, no LLM) → `planner.plan` → `executor.execute` → `summarizer.summarize` → `composer`.
- Planner detects language (`language.py`, +Thai), caps at 5 actions, dedupes, returns `actions:[]` on parse failure.
- Executor checks: known skill → required params → bot/requester permissions (owner bypasses user-side) → role-hierarchy guard for `targets_member` skills → run → `error_mapper` (Discord code map + Friendly fallback).
- Summarizer mirrors user language (forced when detected); falls back to templated reply if its JSON is unparseable.

### 4. Skills (`src/skills/`, 34 total)
- Registry (`__init__.py`): `Skill(name, description, params, execute, required_permissions, targets_member, fetch_raw)`; `params` with `(optional)` = non-required.
- Modules: `channels` (5), `roles` (7), `members` (5), `moderation` (5), `emojis` (4), `invites` (3), `server` (5: info/edit/search/send/snipe).
- `utils/fuzzy_match.py` (mirrors `fuzzyMatch.js`): mention/custom-emoji tags → `#id`/`@id` → raw snowflake → exact → case-insensitive → substring, plus API fetch fallback.
- Deleted-message log lives in `utils/snipe_manager.py`, fed by `bot.py:on_message_delete` for `getSnipe`.

### 5. History (chat mode only, `src/handler/message_handler.py`)
- `_histories: dict[int, deque]` keyed by `channel_id`, `maxlen = HISTORY_LEN*2`.
- `ask_chat()` appends user text then model reply. In-memory only — restart wipes it.
- Agent path is stateless per request (same as Node original).

### 6. Discord wiring (`bot.py` + `src/handler/message_handler.py`)
- Intents: `message_content=True` **required** (also enable in Developer Portal) + `guilds`.
- `on_ready`: `tree.sync()` publishes `/ask` globally (can take ~1h to propagate on first deploy).
- `/ask`: defers, calls `ask_gemini` (chat), sends back in ≤1900-char chunks.
- `on_message`: ignores bots/empty; guild mention → `run_agent` (2s per-user cooldown); empty mention → greeting; DM/auto-channel → `ask_gemini`; replies with `mention_author=False`.
- `on_message_delete`: feeds `skills.server.add_snipe` for `getSnipe`.
- `chunk()`: splits long replies for the 2000-char Discord limit.

## Data flow example (agent mention)

1. User sends `@Bot create a red VIP role and give it to @ploy`.
2. `on_message` → guild mention → `run_agent("create a red VIP role and give it to @ploy", message)`.
3. Prefetch (no LLM) → plan (LLM#1) → `[{createRole}, {addRoleToMember}]`.
4. Executor runs both against Discord, collects success results.
5. Summarize (LLM#2) → "Role **VIP** สร้างและมอบให้ @ploy แล้ว" → chunked reply.

## Constraints / limits

- Free Render worker sleeps on inactivity → use UptimeRobot ping (see DEPLOY.md).
- Gemini free-tier quota per key → rotation helps but N keys ≠ infinite; all-dead raises user-visible error.
- Chat path (DM/auto) has no per-user rate limit yet (spam risk) — see TODO.md. Agent path has 2s cooldown.
- History/snipes unbounded per channel count (memory grows with #channels) — acceptable for small bots.
- Member-name search uses cache; enable Server Members Intent for full servers.
