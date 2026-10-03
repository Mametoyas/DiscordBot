# CHANGELOG.md

## 2026-10-03 — member search fix
- `bot.py`: `intents.members = True` (full member cache; needs portal toggle too).
- `fuzzy_match.py`: strips Thai honorific prefixes (ไอ้/อี/พี่/น้อง/...) before matching, so "ไอ้Nova" finds Nova.

## 2026-10-03 — @Bot chat fallback (flexible mentions)
- `agent/__init__.py`: no-action plan returns `reply=None` (skips summarize, saves 1 call).
- `message_handler.py`: `reply=None` → free chat with per-user memory + capability-aware system prompt (playful, may guess/joke, remembers preferences) instead of stiff refusal. `ask_chat()` accepts `system=`.

## 2026-10-03 — Supabase chat memory (per-user-in-channel)
- `src/utils/chat_store.py` (new): Supabase REST via `httpx` (no new deps) — `get`/`add` keyed `(channel_id, user_id)`, retention prune; silent fallback to local deque on any failure.
- `message_handler.py`: `ask_chat()` uses the store; `/ask` passes `interaction.user.id`. Agent path stays stateless.
- `.env.example`: `SUPABASE_URL`/`SUPABASE_KEY`/`CHAT_KEEP_PAIRS`/`CHAT_RETENTION_DAYS` + setup steps; table SQL lives in `chat_store.SUPABASE_SETUP`.

## 2026-10-03 — /models list|set (owner)
- `bot.py`: command group `/models` — `list` ดูโมเดลที่ใช้ได้ + ตัวปัจจุบัน, `set <name>` เปลี่ยน backbone runtime (ใช้ MODEL_CHOICES เดียวกับ dashboard).

## 2026-09-29 — setRolePermissions + summon mentions (39 skills)
- `roles.py`: `setRolePermissions` (กำหนดสิทธิ์ยศ, `administrator` ได้เฉพาะ owner) + `permissions` ใน `createRole`.
- `prompts.py`: เรียกคน (`เรียก X มา`) เป็น valid social action → ตอบพร้อม @-mention ให้โดน ping.
- `members.py`: `moveAllMembers` (ย้ายยกห้องใน action เดียว ไม่ต้องระบุชื่อ).
- `channels.py`: `extract_layout()` parses pasted `[Category:]` blocks (both layouts tried).
- `planner.py`: injects `restructureServer` with extracted layout when the LLM misses it.
- `editChannel`: `private` (hide/unhide from @everyone) + `allowRoles` (grant view/send/connect).
- `restructureServer`: per-block `private:true` (ADMIN ONLY pattern; children inherit).
- `channels.py`: `restructureServer` (whole category/channel layout in ONE action — bypasses 5-action cap; creates missing, moves existing, never deletes) + `createCategory`. Planner routes big layout requests here.
- `server.py`: `setupServer` (style community/gaming/study; never deletes, skips existing, posts welcome message). Planner routes vague "จัดเซิร์ฟเวอร์" here instead of asking for names.
- Deleted `src/skills/voice.py`, `lavalink/`, music slash (`/play`…), Lavalink wiring, `wavelink/PyNaCl/davey` deps, `LAVALINK_*` config. Reason: public nodes unreliable + 315MB RAM too tight. Music lives on in the `music` branch if needed later.
- Planner scope: music out-of-scope again. Slash now 5: `/ask /help /model /addkey /llmstatus`.

## 2026-09-29 — ACLClouds guide (4-day renewal)
- `DEPLOY-ACLCLOUDS.md`: free Python bot steps + renewal reminder + music env.
- `DEPLOY-WAIFLY.md`: free Python host guide (File Manager upload, startup cmd, auto-restart).
- `DEPLOY-FREE.md`: Quaxly (bot, 24/7) + public Lavalink SG node (music, no Java hosting). `.env.example` documents the public node.
- `DEPLOY-RAILWAY.md`: 2 services + private network (`lavalink.railway.internal:2333`), trial $5 notes.
- `Dockerfile` (bot, slim) + `DEPLOY-HF.md`: 2 Spaces (bot + lavalink), secrets via Space Variables, `PORT=7860`.
- `bot.py`: `/help` สรุปวิธีใช้ (คุย/agent/เพลง/pagination/admin), ephemeral.
- `voice.py` refactored: skills delegate to public `do_*` core, shared with slash.
- `bot.py`: `/play` (autocomplete suggest from Lavalink, ≤25 choices), `/skip`, `/stop`, `/queue`, `/leave`. Guild-only.
- `src/handler/paginator.py`: long replies split on line boundaries + ◀ n/N ▶ buttons (author-only, 120s timeout then disabled). Wired into all message replies; `/ask` still uses `chunk()` followups.
- `lavalink/`: Dockerfile (Lavalink v4 + youtube-plugin 1.18.2, heap capped 300M) + minimal application.yml.
- `render.yaml`: new `discord-lavalink` docker service; bot gets `LAVALINK_HOST` (+password, must match).
- `requirements.txt`: `wavelink>=3.0`. `bot.py`: `voice_states` intent, pool connect in `on_ready`, `on_wavelink_track_end` queue advance (autoplay OFF).
- `src/skills/voice.py`: 9 skills (join/leave/play/stop/skip/queue/now/pause/volume). Planner scope now allows music.
- Docs: DEPLOY lavalink notes, TESTER voice checklist, SKILL.md catalog + scope.
- New `src/web/server.py`: stdlib-only dashboard in the same process (daemon thread). Status pill + metrics, switch-model dropdown, add-key box, dark terminal log with 2s polling. Auth via `ADMIN_TOKEN` (`X-Admin-Token`); writes 403 without it.
- `bot.py` starts web server on `PORT` (Render provides it; local default 8080).
- `render.yaml`: worker → **web service** + `healthCheckPath: /api/status` + `ADMIN_TOKEN` env. UptimeRobot now works (real HTTP port).
- `.env.example`: `ADMIN_TOKEN`, `PORT`.
- `src/core/llm.py`: `set_model()` / `add_keys()` / `status()` (rebuilds rotation cycle, clears cooldowns on switch).
- `bot.py`: owner-only slash `/model [name]`, `/addkey <key>`, `/llmstatus` (ephemeral replies). Runtime changes revert on restart — Render env stays source of truth.
- Default backbone `gemini-2.0-flash` → `gemini-3.5-flash-lite` (old model quota 0/0/0).

## 2026-09-29 — Mirror discord-bot-agents/src layout
- Restructured Python code to `src/` mirroring the Node tree: `agent/` (+`language.py`, `composer.py`, trigger-based `prefetch.py` with `skill.fetch_raw` on 5 skills), `config.py`, `core/llm.py`, `handler/message_handler.py`, `skills/` (34), `utils/` (`fuzzy_match` with extractId/normalize + API fallback, `error_mapper` with Discord code map, `json_helper` with fence/repair/loose-field parsing, `snipe_manager`).
- `bot.py` is now a thin entry (same `python bot.py` start command; Procfile/render.yaml untouched).
- Chat history + chunking moved to `handler/message_handler.py`; mention detection hardened with `config.BOT_PREFIX`.
- Not ported (documented): multi-provider failover (single Gemini rotator), Components V2 UIs, jobManager/promptSplitter/retry/uiBuilder utils.
- Live-token verification still pending.
- New `llm.py`: `GeminiRotator` moved out of `bot.py` + `generate_text()` + `extract_json()` (planner/summarizer use).
- New `skills/`: 34 skills ported (channels/roles/members/moderation/emojis/invites/server) + `resolve.py` mention/ID/name lookup + registry with `required_permissions` / `targets_member`.
- New `agent/`: `run()` = prefetch → plan (temp 0, max 5 actions, dedupe) → execute (perm + hierarchy guards, error mapping) → summarize with fallback.
- `bot.py`: guild `@Bot` mention → agent; empty mention → greeting (0 LLM); DM/auto-channel → chat as before; `/ask` → chat; `on_message_delete` snipe log; 2s agent cooldown.
- New Agent Skill `discord-bot-agent` in `~/.agents/skills/` (validated ✅): SKILL.md + skill-catalog/agent-prompts/scope-rules references.
- Simplifications vs Node original: single Gemini provider (rotation kept, 10-provider failover not ported), plain-text replies (no Components V2), in-memory history/snipe.
- Live-token verification still pending.
- Added `AGENT.md`, `PLAN.md`, `ARCHITECTURE.md`, `QA.md`, `DEPLOY.md`, `TESTER.md`, `TODO.md`, `README.md`, `CHANGELOG.md`.
- No code changes to `bot.py`. Live-token verification still pending.

## 2026-09-29 — Core bot + Render config
- `bot.py`: Discord gateway client, slash `/ask`, mention/DM/auto-channel reply, `GeminiRotator` multi-key rotation over raw Gemini REST, per-channel in-memory history.
- `requirements.txt` (`discord.py`, `httpx`, `python-dotenv`), `Procfile` (worker), `render.yaml` (worker, Python 3.11.9), `.env.example`, `.gitignore`.
