# DEPLOY-FREE.md — โฮสต์บอทฟรี ไม่ใช้บัตร (Quaxly + Lavalink สาธารณะ)

Render/Railway/Koyeb/HF-Docker ล้วนติดบัตร — ทางนี้ไม่ต้องมีบัตรเลย

## 1. บอท → Quaxly (ฟรีถาวร, 24/7, ไม่ใช้บัตร)

1. สมัคร quaxly.com (email อย่างเดียว) → Create → เลือก **Python**
2. อัปโหลดไฟล์: `bot.py`, `requirements.txt`, ทั้งโฟลเดอร์ `src/` (ไม่ต้องเอา `lavalink/`, `discord-bot-agents/`, `Dockerfile`, `render.yaml`)
3. Start command: `python bot.py`
4. Environment variables (ใส่ใน panel, ห้ามใส่ในโค้ด):
   - `DISCORD_TOKEN`, `GEMINI_KEYS`, `GEMINI_MODEL=gemini-3.5-flash-lite`
   - `LAVALINK_HOST=https://lavalink.jirayu.net` (node ไทย, ดีเลย์ต่ำสุด)
   - `LAVALINK_PASSWORD=youshallnotpass`
   - `ADMIN_TOKEN` = สตริงยาวๆ (dashboard ใช้ไม่ได้บนนี้ — ข้ามได้)
5. กด Start → ดู Logs มี `Logged in as` + `Lavalink connected` = จบ

ทางเลือกสำรองสเปกใกล้กัน: Waifly (300MB, 24/7, ไม่ใช้บัตร, panel แบบ Pterodactyl)

## 2. เพลง → Lavalink สาธารณะ (ไม่ต้อง host Java เอง)

บอทต่อ node สาธารณะผ่าน `LAVALINK_HOST/PASSWORD` อยู่แล้ว ไม่ต้องแก้โค้ด:

| Node | HOST | PASSWORD | หมายเหตุ |
|---|---|---|---|
| 🇹🇭 ไทย (แนะนำ) | `https://lavalink.jirayu.net` | `youshallnotpass` | v4, ดีเลย์ต่ำสุด |
| 🌍 สำรอง 1 | `https://lavalink-v4.triniumhost.com` | `free` | v4 |
| 🌍 สำรอง 2 | `https://lavalinkv4.serenetia.com` | `https://seretia.link/discord` | v4 |

node สาธารณะดับ/เปลี่ยนรหัสได้ — ถ้าเพลงเล่นไม่ได้ให้เช็คลิสต์สดที่ `lavalink-list.darrennathanael.com` หรือ `lavainfo.netlify.app` แล้วเปลี่ยนแค่ 2 env นี้ (ไม่ต้อง redeploy โค้ด ถ้า host มีปุ่ม restart: restart หนึ่งที)

## 3. ตรวจงาน (เหมือนเดิม)

`/help` → `@Bot list channels` → เข้าห้องเสียง → `/play` ต้องมี suggest → `Lavalink connected` ใน logs

## ข้อจำกัดของทางฟรี

- RAM รวม ~512MB shared — บอทเราตัวเดียวพอ (idle ~100MB) อย่ารันอย่างอื่นร่วม
- node เพลงสาธารณะ = ของคนอื่น (ช้ากว่า/ดับได้) รับได้ค่อยขยับไป self-host ทีหลัง
- ประวัติแชท/คิวเพลงหายเมื่อ restart (in-memory ตามเดิม)
