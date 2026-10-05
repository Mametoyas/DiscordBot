# Discord Gemini Bot — now with Server-Management Agent

Discord AI bot using hosted **Gemini API** — no local LLM, no own server. Runs as a worker on **Render**.

- `@Bot <คำสั่งจัดการ server>` → **agent** (plan → execute → summarize, 49 skills)
- `@Bot จัดเซิร์ฟเวอร์ให้หน่อย` → สร้าง layout มาตรฐาน (general/rules/welcome/ห้องเสียง + ข้อความต้อนรับ) ไม่ลบของเดิม
- `@Bot จัดหมวดหมู่ + ย้ายห้องตามผังนี้ ...` → สร้าง categories + สร้าง/ย้ายห้องทีเดียวจบ (แปะผังมาได้เลย)
- `@Bot` ลอยๆ → greeting (no LLM call)
- `/ask <question>` → chat Q&A (Gemini)
- `/help` → วิธีใช้ทั้งหมด (ephemeral, เห็นคนเดียว)
- `/model [name]` → ดู/เปลี่ยน backbone runtime (owner only, มีผลทันทีไม่ต้อง restart)
- `/addkey <key>` → เพิ่ม API key ตอนรัน (owner only, ephemeral)
- `/llmstatus` → ดู model + จำนวน keys (owner only)
- Every message in `AUTO_REPLY_CHANNEL_IDS` + DM → chat Q&A
- Chat memory is **channel-shared** (group-chat style: everyone in the channel shares one pool, messages labeled `Name:`) + auto-**backfills** recent Discord history on first use, persisted to **Supabase** (`SUPABASE_URL`/`SUPABASE_KEY`; SQL in `src/utils/chat_store.py`) — survives restart; falls back to in-memory if unset
- Custom member nicknames (`@Bot จำไว้ว่าไอ้เสือคือ @X`) stored in Supabase `member_aliases` (+ local fallback); name search tries username → server nick → remembered alias → substring
- Shared guild memory (`@Bot จำไว้ว่า...` / `ลืมเรื่อง...`) in Supabase `memories`, auto-injected into the planner; long chat histories compress into summaries
- Destructive skills (kick/ban/clear/delete channel/thread) ask ✅/❌ confirmation first (requester-only, 60s)
- Multi-key rotation: `GEMINI_KEYS=key1,key2,key3` auto-switches on 429/quota

## Quickstart (local)

```powershell
Copy-Item .env.example .env   # then fill tokens
pip install -r requirements.txt
python bot.py
```

Required env: `DISCORD_TOKEN`, `GEMINI_KEYS`. Optional: `GEMINI_MODEL` (default `gemini-2.0-flash`), `AUTO_REPLY_CHANNEL_IDS`, `HISTORY_LEN`, `SYSTEM_PROMPT`, `BOT_NAME`.

Tests: `python -m unittest discover tests` (stdlib only).

Also enable **MESSAGE CONTENT INTENT** + **SERVER MEMBERS INTENT** in the Discord Developer Portal (Bot → Privileged Gateway Intents) and invite with `bot` + `applications.commands` scopes. Without Members Intent, name search only sees cached members.

## Layout (mirrors `discord-bot-agents/src/`)

- `bot.py` — thin entry: client + `/ask` + events (keeps `Procfile`/`render.yaml` as `python bot.py`)
- `src/config.py` — env loading
- `src/core/llm.py` — `GeminiRotator` + `generate_text()`
- `src/skills/` — 49 skills in 9 modules + registry
- `lavalink/` — Dockerfile + application.yml (Lavalink v4 + youtube-plugin 1.18.2)
- `src/agent/` — `run()` = prefetch → planner → executor → summarizer + `language.py` + `composer.py`
- `src/handler/message_handler.py` — mention/cooldown/greeting + agent/chat routing (+`paginator.py` ปุ่ม ◀ 1/3 ▶)
- `src/utils/` — `fuzzy_match.py` / `error_mapper.py` / `json_helper.py` / `snipe_manager.py`
- `src/web/server.py` — admin dashboard per DESIGN.md (status pill, switch-model dropdown, add-key, terminal log; stdlib only)
- `discord-bot-agents/` — reference Node.js implementation (read-only)
- Reusable Agent Skill: `~/.agents/skills/discord-bot-agent/` (`SKILL.md` + catalog/prompts/scope references)

## Dashboard

Local `http://localhost:8080` · Render service URL. Online pill, model/keys/servers/latency/uptime, add-key box, live terminal log. Write actions need `ADMIN_TOKEN` env (browser asks once, remembered locally).

## Docs for contributors / AI agents

| Doc | Use |
|---|---|
| `AGENT.md` | **Start here** (repo map + rules) |
| `PLAN.md` | Status + what's next |
| `ARCHITECTURE.md` | How `bot.py` works |
| `QA.md` | Decisions + FAQ (e.g. why not Vercel) |
| `TESTER.md` | Verification checklists |
| `DEPLOY.md` | Render runbook |
| `TODO.md` | Backlog |
| `CHANGELOG.md` | History of changes |

## Deploy

Render → New → Blueprint → select repo → set env vars → Deploy. Full steps in `DEPLOY.md`.
No card? Hugging Face Spaces (free forever, sleeps) — `DEPLOY-HF.md`. Trial credit, no sleep — `DEPLOY-RAILWAY.md`. **Free forever, no card, 24/7 — `DEPLOY-FREE.md`** (Quaxly + public Lavalink; Quaxly เต็ม → `DEPLOY-WAIFLY.md`; สำรองแบบต่ออายุเอง → `DEPLOY-ACLCLOUDS.md`).
