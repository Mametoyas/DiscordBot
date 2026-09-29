# DEPLOY-WAIFLY.md — Waifly (ฟรีถาวร ไม่ใช้บัตร 300MB รัน 24/7)

Quaxly ไม่มี node ว่างให้ free tier —  Gerrit ใช้ Waifly แทน (panel Pterodactyl)

## 1. สร้าง server

1. สมัคร dash.waifly.com → **Create** → เลือก **Python Egg** → ตั้งชื่อ → location Paris
2. อัปโหลดไฟล์ผ่าน File Manager: `bot.py`, `requirements.txt`, ทั้งโฟลเดอร์ `src/` (ไม่เอา `lavalink/`, `Dockerfile`, `render.yaml`, `discord-bot-agents/`)
3. Startup command: `python bot.py` (dependencies จาก `requirements.txt` ลงเองตอนสตาร์ท)

## 2. ใส่ env (Variables / Environment tab)

- `DISCORD_TOKEN`, `GEMINI_KEYS`, `GEMINI_MODEL=gemini-3.5-flash-lite`
- `LAVALINK_HOST=https://sg.lavalink.heavencloud.in`
- `LAVALINK_PASSWORD=heavencloud`
- (`ADMIN_TOKEN` ข้ามได้ — dashboard เปิดจากข้างนอกไม่ได้อยู่แล้ว)

## 3. เปิด + กันดับ

1. กด **Start** → ดู console ต้องมี `Logged in as` + `Lavalink connected`
2. เปิด **auto-restart** (กัน crash แล้วดับยาว — ครบ 3 วัน offline โดน suspend)
3. ในดิส: `/help` → `@Bot list channels` → เข้าห้องเสียง → `/play` ต้องมี suggest

## ข้อจำกัด

- CPU แคป 30% + RAM 300MB — บอทเราพอ (idle ~100MB) ห้ามรันอย่างอื่นร่วม
- ห้าม VPN/proxy/tunnel + ห้าม obfuscate โค้ด (กฎ anti-abuse) — โค้ดเราปกติ ผ่าน
- เพลงใช้ node สาธารณะเหมือนเดิม (ดับค่อยเปลี่ยน US/EU ตาม `DEPLOY-FREE.md`)
