# DEPLOY-ACLCLOUDS.md — ACLClouds (ฟรี ไม่ใช้บัตร 24/7 ต่ออายุทุก 4 วัน)

## 1. สมัคร + สร้างบอท

1. สมัครที่ aclclouds.com (ดูหน้า `/en/bots` สำหรับแพ็กฟรี)
2. สร้าง **bot service ใหม่** → runtime **Python** (discord.py/Pycord)
3. อัปโหลดไฟล์: `bot.py`, `requirements.txt`, ทั้งโฟลเดอร์ `src/` (ไม่เอา `Dockerfile`, `render.yaml`, `discord-bot-agents/`)

## 2. ตั้งค่า start + env

1. Start command: `python bot.py` (dependencies จาก `requirements.txt`)
2. Environment variables ใน panel:
   - `DISCORD_TOKEN`, `GEMINI_KEYS`, `GEMINI_MODEL=gemini-3.5-flash-lite`
3. เปิด **automatic restart** (กัน crash แล้วดับ)

## 3. ตรวจงาน

- Live logs ต้องมี `Logged in as` + `Slash commands synced`
- ในดิส: `/help` → `@Bot list channels` → `/ask สวัสดี`

## 4. สำคัญ: ต่ออายุทุก 4 วัน

- ฟรีแพลนต้องกด **renew/manual renewal เองทุก 4 วัน** ไม่งั้นดับ (ไฟล์ไม่หาย กลับมากด start ใหม่ได้)
- ตั้งเตือนในมือถือไว้ (เช่น ทุกวันจันทร์+ศุกร์) — ใช้เวลาไม่ถึงนาที
- อยากเลิกกด: ย้ายไป VPS เสียตัง (~100 บาท/เดือน) จบถาวร
