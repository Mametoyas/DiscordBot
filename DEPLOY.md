# DEPLOY.md — Render Runbook

> หมายเหตุ: ฟีเจอร์เพลงถูกถอดออกแล้ว — ข้ามขั้นตอน Lavalink ทั้งหมด (service ที่ 2 + env `LAVALINK_*`)

Target: `render.yaml` **web service** `discord-gemini-bot`, Python 3.11.9, `pip install -r requirements.txt` → `python bot.py` (Discord gateway + admin dashboard in one process, health check `/api/status`).

## Prerequisites

- [ ] GitHub repo contains: `bot.py`, `requirements.txt`, `Procfile`, `render.yaml`, `src/`
- [ ] Discord: token + `MESSAGE CONTENT INTENT` ON + bot invited with `bot` + `applications.commands` scopes
- [ ] 1–3 Gemini keys (aistudio.google.com)
- [ ] (Optional) auto-reply channel ID(s)
- [ ] (Optional) `ADMIN_TOKEN` — enables dashboard write actions (switch model / add key)

## Deploy steps

1. Push to GitHub (`main`).
2. Render dashboard → **New → Blueprint** → select repo → Apply (reads `render.yaml`).
3. Set env vars (dashboard → Service → Environment):
   - `DISCORD_TOKEN` = `<bot token>`
   - `GEMINI_KEYS` = `key1,key2,key3` (no spaces needed)
   - `GEMINI_MODEL` = `gemini-3.5-flash-lite` (already default in yaml)
   - `AUTO_REPLY_CHANNEL_IDS` = `<channel_id>` (optional)
   - `ADMIN_TOKEN` = `<long random string>` (optional but recommended)
   - `LAVALINK_HOST` = `https://discord-lavalink.onrender.com` (already default in yaml)
   - `LAVALINK_PASSWORD` = `<same value as the lavalink service>` (must match!)
4. **Deploy** → Blueprint creates 2 services: bot + `discord-lavalink`. Watch bot Logs for:
   - `Admin dashboard on :10000` → web OK (Render sets `PORT` itself)
   - `Logged in as <BotName>` → gateway OK
   - `Slash commands synced` → slash registered
   - `Lavalink connected` → music ready (if missing: check `LAVALINK_PASSWORD` matches on both services)
5. Open the service URL → dashboard: online pill, metrics, add-key box, live log.
6. In Discord: mention the bot, try `/ask`, send a message in the auto channel.
7. (Free tier) Web services sleep when idle — UptimeRobot HTTP monitor on the service URL keeps it awake (now possible: it has a real HTTP port).

## Music (Lavalink) notes

- Two services, one password: set the SAME `LAVALINK_PASSWORD` on `discord-gemini-bot` AND `discord-lavalink`, then redeploy both.
- `LAVALINK_HOST` default assumes the lavalink service is named `discord-lavalink` (URL `https://discord-lavalink.onrender.com`). Renamed it? Update the bot env to match.
- Free-tier RAM ≈512MB: the Dockerfile caps JVM heap at 300MB (`JAVA_TOOL_OPTIONS`). If Lavalink OOMs, shrink queue/playlist limits in `lavalink/application.yml`.
- YouTube breakage: if playback starts 403ing, the youtube-plugin needs a PO token (OAuth block) — check plugin releases, add its config to `application.yml`, redeploy the lavalink service only.
- Local dev: `docker run -p 2333:2333 -e LAVALINK_PASSWORD=devpass -v ./lavalink/application.yml:/opt/Lavalink/application.yml <image>` then `LAVALINK_HOST=http://localhost:2333` in `.env`.

## Rollback

- Render → Deploys → Redeploy previous commit. Env vars are preserved.

## Common failures

| Symptom | Cause → Fix |
|---|---|
| `❌ ไม่เจอ DISCORD_TOKEN` at boot | Env var missing/typo → set it, Manual Deploy |
| `❌ ไม่เจอ GEMINI_KEYS` | Same as above |
| Online but silent | `MESSAGE CONTENT INTENT` off in portal, or channel not in auto-list and no mention |
| `401 Unauthorized` Gemini | Revoked/bad key → replace that key in `GEMINI_KEYS` |
| Repeated `โดน limit` then user error | Quota exhausted on all keys → add keys / wait / reduce `maxOutputTokens` |

## Env contract (keep in sync)

If you rename/add an env var, update ALL of: `src/config.py` loader, `.env.example`, `render.yaml`, this file.
