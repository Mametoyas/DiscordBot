# DEPLOY-HF.md — Hugging Face Spaces (ฟรี, ไม่ต้องผูกบัตร)

รัน 2 Spaces คู่กัน: `discord-bot` (Python) + `discord-lavalink` (Java).
Render Blueprint ใช้ไม่ได้ถ้าไม่มีบัตร (Docker service บังคับ paid) — ทางนี้แทน

## A. Lavalink Space (ทำก่อน)

1. huggingface.co → New Space → ตั้งชื่อเช่น `discord-lavalink` → SDK **Docker** → Blank → Create
2. Clone Space ลงเครื่อง:
```powershell
git clone https://huggingface.co/spaces/<user>/discord-lavalink
Copy-Item lavalink\Dockerfile,lavalink\application.yml discord-lavalink\
```
3. สร้าง `README.md` ในโฟลเดอร์นั้น เนื้อหา:
```
---
title: Discord Lavalink
sdk: docker
app_port: 7860
---
```
4. ใน Space → Settings → Variables: `LAVALINK_PASSWORD` = รหัสยาวๆ, `PORT` = `7860`
5. `git add .; git commit -m "lavalink"; git push` → รอ build → ได้ URL `https://<user>-discord-lavalink.hf.space`
6. เช็คว่าติด: เปิด `https://<user>-discord-lavalink.hf.space/v4/info` ควรได้ 401 (แปลว่า server ตอบแล้ว แค่ยังไม่ใส่รหัส = ปกติ)

## B. Bot Space

1. New Space ชื่อ `discord-bot` → SDK **Docker** → Blank
2. Clone แล้ว copy ทั้ง repo (ยกเว้น `discord-bot-agents/`, `.env`):
```powershell
git clone https://huggingface.co/spaces/<user>/discord-bot botspace
# copy: bot.py Dockerfile requirements.txt render.yaml Procfile src/ lavalink/ *.md .env.example
```
3. `README.md`:
```
---
title: Discord Bot
sdk: docker
app_port: 7860
---
```
4. Settings → Variables (ห้ามใส่ในโค้ด):
   - `DISCORD_TOKEN`, `GEMINI_KEYS`, `GEMINI_MODEL=gemini-3.5-flash-lite`
   - `LAVALINK_HOST=https://<user>-discord-lavalink.hf.space`
   - `LAVALINK_PASSWORD` = **ค่าเดียวกับข้อ A**
   - `ADMIN_TOKEN` = สตริงยาวๆ, `PORT=7860`
5. Push → รอ build → ดู Logs ฝั่ง Space ต้องมี `Logged in as` + `Lavalink connected`

## C. กันหลับ + ตรวจงาน

- UptimeRobot ping URL ทั้ง 2 Spaces ทุก 5 นาที (Spaces หลับตอนเงียบนาน ตื่นช้า ~1 นาที)
- ในดิส: `/help` → `@Bot list channels` → เข้าห้องเสียง → `/play` ต้องมี suggest
- เปิด URL bot Space = dashboard (ใส่ ADMIN_TOKEN ตอนมันถาม)

## ข้อจำกัด vs Render

- Cold start ช้ากว่า (Java บน CPU shared) — เพลงแรกของวันอาจรอ ~1-2 นาที
- ถ้า Spaces คู่กันหลับพร้อมกัน เพลงจะ reconnect เองเมื่อตื่น (บอท reconnect Lavalink ตอน `on_ready` เท่านั้น — ถ้า lavalink ตื่นทีหลัง ให้ restart bot Space หนึ่งที)
