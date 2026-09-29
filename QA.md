# QA.md — Decisions & Frequently Asked Questions

> Append-only. New agent: add rows here when you make a load-bearing decision.

## Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Run LLM locally or via API? | Hosted Gemini API | User has no GPU server; free-tier keys are enough |
| 2 | Render vs Vercel for the full bot? | **Render (worker)** | Bot needs persistent websocket for mention + auto-reply. Vercel = serverless HTTP only, cannot hold a gateway connection. Vercel could only serve slash commands via Interactions webhook (separate architecture, not built). |
| 3 | `google-generativeai` SDK vs raw REST? | Raw REST via `httpx` (`src/core/llm.py`) | Multi-key rotation + error inspection is simpler without SDK version churn; endpoint `v1beta/models/{model}:generateContent` |
| 4 | Single file vs cogs/modules? | Single `bot.py` (<250 lines) | Easier handover; split only after >500 lines |
| 5 | History storage? | In-memory `deque` per channel | Zero infra; lost on restart — acceptable for v1 (Redis later if needed) |
| 6 | How to support "bot's own channel" auto-reply? | `AUTO_REPLY_CHANNEL_IDS` env (comma-separated IDs) | Explicit, no fragile name-matching; empty = mention/DM only |
| 7 | Port discord-bot-agents agent to Python — full or condensed? | Condensed: same plan→execute→summarize + all 34 skills, but **single Gemini provider** (existing `GeminiRotator`), plain-text replies | 10-provider failover + Components V2 UIs are Node/discord.js-specific; porting them adds deps without user benefit. Registry shape allows adding providers later. |
| 8 | discord.py vs discord.js Components V2 (paginated UIs, containers)? | discord.py `View` buttons: `src/handler/paginator.py` (◀ n/N ▶, author-only, 120s) for any reply spanning pages | Line-boundary split so list rows never break; containers/embeds still plain text. |
| 9 | Where does `@Bot` mention go — chat or agent? | Guild mention → **agent**; DM/auto-channel/`/ask` → **chat** | Preserves req-3 chat modes while giving server-management powers on mention. Empty mention → greeting, 0 LLM (same as Node handler). |
| 10 | Agent Skill location? | Global `~/.agents/skills/discord-bot-agent/` (validated ✅) | Reusable across projects; repo keeps the Python runtime. Init via skill-creator `init-skill.mjs`, references linked with relative paths. |
| 11 | Music? | **Removed 2026-09-29** (was Lavalink v4 + wavelink; public nodes too flaky, RAM too tight) | Code deleted (`voice.py`, `lavalink/`, music slash); scope back to no-music. Re-add from git history (`music` branch) if self-hosting later. |

## FAQ

**Q: Where do I get the tokens?**
A: Discord token: discord.com/developers → App → Bot → Reset Token + enable `MESSAGE CONTENT INTENT` + invite via OAuth2 URL Generator (scopes `bot`, `applications.commands`). Gemini keys: aistudio.google.com → Get API key (create 2–3 keys for rotation).

**Q: Bot is online but doesn't reply to normal messages?**
A: Expected unless the channel ID is in `AUTO_REPLY_CHANNEL_IDS`. Mention it (→ agent in guilds) or use `/ask`. Also check `MESSAGE CONTENT INTENT` is ON both in portal and code (`bot.py` intents).

**Q: Agent says it can't find a member by name?**
A: Name search uses the member cache. Enable **SERVER MEMBERS INTENT** in the portal (and add `intents.members = True` in `bot.py`) for full servers; mentions/raw IDs always work.

**Q: `/ask` doesn't appear?**
A: `tree.sync()` can take up to ~1h on first global sync. Re-invite the bot with `applications.commands` scope, then wait / kick + re-invite.

**Q: "Gemini ทุกคีย์ใช้ไม่ได้: HTTP 429"?**
A: All keys exhausted. Add more keys (comma-separated) or wait. Check Render logs for `โดน limit -> พัก 60s` lines to confirm rotation happened.

**Q: How do I find a channel ID?**
A: Discord Settings → Advanced → Developer Mode ON → right-click channel → Copy Channel ID.

**Q: Can I change the model / personality?**
A: Yes — env `GEMINI_MODEL` (e.g. `gemini-2.0-flash`, `gemini-1.5-pro`) and `SYSTEM_PROMPT`. No code change needed.

**Q: Why does history mix users together?**
A: Known v1 limitation — history is per-channel, not per-user. Per-user threads are in TODO.md.
