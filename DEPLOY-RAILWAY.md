# DEPLOY-RAILWAY.md — Railway (trial $5 ไม่ต้องผูกบัตร, ไม่ sleep)

> หมายเหตุ: ฟีเจอร์เพลงถูกถอดออกแล้ว — สร้างแค่ service บอท service เดียวพอ

รัน 2 services ใน project เดียว คุยกันผ่าน private network (ไม่เปิดสู่เน็ต)

## 1. สร้าง project

1. railway.app → **New Project → Deploy from GitHub repo** → เลือก `Mametoyas/DiscordBot`
2. ได้ service แรก = **บอท** (root `Dockerfile` ถูกใช้เองอัตโนมัติ) → ตั้งชื่อ `bot`

## 2. เพิ่ม Lavalink service

1. ใน project กด **+ New → GitHub Repo** → เลือก repo เดิม
2. Service ใหม่ → **Settings → Build**: `Root Directory` = `lavalink` (Dockerfile + application.yml ถูกใช้ตามนั้น)
3. ตั้งชื่อ service `lavalink`

## 3. ใส่ Variables

ฝั่ง `bot` (Variables tab):
- `DISCORD_TOKEN`, `GEMINI_KEYS`, `GEMINI_MODEL=gemini-3.5-flash-lite`
- `LAVALINK_HOST=http://lavalink.railway.internal:2333` (ชื่อ service ตามข้อ 2 + port 2333)
- `LAVALINK_PASSWORD` = รหัสยาวๆ
- `ADMIN_TOKEN` = สตริงยาวๆ
- (`PORT` Railway ใส่ให้เอง ห้ามทับ)

ฝั่ง `lavalink`:
- `LAVALINK_PASSWORD` = **ค่าเดียวกับฝั่งบอท**
- `PORT` = `2333`

## 4. ตรวจงาน

- Deploy Logs ทั้งคู่ต้องเขียว; ฝั่งบอทมี `Logged in as` + `Lavalink connected`
- ในดิส: `/help` → `@Bot list channels` → เข้าห้องเสียง → `/play` มี suggest
- อยากเปิด dashboard: ฝั่งบอท → Settings → Networking → **Generate Domain** → เปิด URL (ใส่ ADMIN_TOKEN ตอนถาม)

## 5. คุมค่าใช้จ่าย (สำคัญ)

- Trial ให้ **$5 ใช้ครั้งเดียวหมดแล้วหมดเลย** (ไม่รีทุกเดือน) 2 services กิน ~$5–10/เดือน → เงินหมดบอทดับ
- ดูที่ Usage tab; ตั้ง Service → Settings → **Resource Limits** (bot 256MB / lavalink 512MB) กันไหล
- เงินหมดแล้วไม่อยากจ่าย → ย้ายไป `DEPLOY-HF.md` (ฟรีถาวรแต่หลับได้)
