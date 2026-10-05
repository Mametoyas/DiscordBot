# DEPLOY-RAILWAY.md — Railway (CI/CD, ไม่ sleep)

> ฟีเจอร์เพลงถูกถอดแล้ว — เหลือ service บอท service เดียว

## 1. สร้าง project

1. railway.app → **New Project → Deploy from GitHub repo** → เลือก `Mametoyas/DiscordBot`
2. ได้ service `bot` (ใช้ `Dockerfile` ที่ root อัตโนมัติ)

## 2. ใส่ Variables (ฝั่ง `bot`, tab Variables)

- `DISCORD_TOKEN`, `GEMINI_KEYS`, `GEMINI_MODEL=gemini-3.5-flash-lite`
- `GROQ_API_KEY` (ถ้าใช้ backbone ฝั่ง Groq)
- `SUPABASE_URL`, `SUPABASE_KEY` (+ `SUPABASE_DB_URL` ถ้าอยากให้บอทสร้างตารางเอง)
- `ADMIN_TOKEN` (สำหรับ dashboard), `AUTO_REPLY_CHANNEL_IDS` (ถ้ามี)
- (`PORT` Railway ใส่ให้เอง ห้ามทับ)

## 3. CI/CD

- ต่อ repo ไว้ → ทุก `git push` ขึ้น `main` deploy ใหม่อัตโนมัติ ไม่ต้องกดเอง

## 4. ตรวจงาน

- Deploy Logs ต้องเขียว มี `Logged in as` + `Slash commands synced` (+ `[DB] tables ensured` ถ้าตั้ง `SUPABASE_DB_URL`)
- ในดิส: `/help` → `/llmstatus` → `@Bot ...` (อย่าลืมแท็ก)
- อยากเปิด dashboard: Settings → Networking → **Generate Domain** → เปิด URL (ใส่ `ADMIN_TOKEN` ตอนถาม)

## 5. คุมค่าใช้จ่าย (สำคัญ)

- Trial ให้ **$5 ใช้ครั้งเดียวหมดแล้วหมดเลย** (ไม่รีทุกเดือน) บอทตัวเดียวกิน ~$2–5/เดือน → เงินหมดบอทดับ
- ดูที่ Usage tab; ตั้ง Service → Settings → **Resource Limits** (bot 256MB) กันไหล
- เงินหมดแล้วไม่อยากจ่าย → ย้ายไป `DEPLOY-HF.md` (ฟรีถาวรแต่หลับได้) หรือ `DEPLOY-ACLCLOUDS.md` (ฟรี กด renew ทุก 4 วัน)
