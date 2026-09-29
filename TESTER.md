# TESTER.md — How to Verify Changes

## Environment note

> This dev machine (Windows, Sep 2026) has **no Python** (`py -3` broken). Do all syntax/live tests on a machine with Python 3.11+ or in Render logs.

## A. Static check (any Python machine)

```powershell
py -3 -m py_compile bot.py src\config.py src\core\llm.py src\agent\*.py src\skills\*.py src\handler\*.py src\utils\*.py
pip install -r requirements.txt
```

## B. Unit-ish checks (no Discord token needed)

```powershell
$env:GEMINI_KEYS="dummy"
py -3 -c "from src.skills import SKILLS; print('skills:', len(SKILLS))"
# rotation logic smoke test (offline, expects RuntimeError, proves retry loop runs):
py -3 -c "import os; os.environ['GEMINI_KEYS']='bad1,bad2'; from src.core.llm import GeminiRotator; print('rotator keys:', GeminiRotator(['bad1','bad2']).key_count)"
```

Recommended next step for an agent: add `tests/test_rotator.py` mocking `httpx` (429 → next key, 200 → text). Not yet written — see TODO.md.

## C. Live test (needs real tokens)

1. Copy `.env.example` → `.env`, fill `DISCORD_TOKEN`, `GEMINI_KEYS` (2 keys to test rotation), `AUTO_REPLY_CHANNEL_IDS`.
2. `py -3 bot.py` → expect logs `Logged in as ...` + `Slash commands synced`.
3. In a test guild:
   - [ ] `@Bot สวัสดี` → agent replies (greeting/identity, no skill needed)
   - [ ] `@Bot list channels` → agent runs `listChannels`, lists real channels
   - [ ] Long list (many channels/roles) → single reply with ◀ 1/N ▶ buttons; only the requester can flip; buttons disable after ~2 min
   - [ ] `@Bot create text channel test-bot` → channel created (needs Manage Channels + hierarchy OK)
   - [ ] `@Bot` alone → greeting, no LLM call
   - [ ] Voice (join a voice channel first): `@Bot เปิดเพลง <ชื่อเพลง>` → bot joins + plays; `@Bot คิวเพลง` → queue; `@Bot ข้าม` → next; `@Bot หยุดเพลง` → stops; `@Bot ออกห้อง` → leaves
   - [ ] `/play` → พิมพ์ 2-3 ตัวอักษรมี suggest เพลงเด้ง, เลือกแล้วเล่นทันที; `/queue` `/skip` `/stop` `/leave` ทำงาน
   - [ ] `/ask ทดสอบ` → chat reply (slash path, `bot.py`)
   - [ ] Plain message in auto channel → chat reply; plain message elsewhere → silent
   - [ ] DM the bot → chat reply
   - [ ] Long answer → split into multiple messages, no 2000-char error
4. Rotation test: temporarily set key #1 to an invalid string → send 2 prompts → logs show `โดน limit` and reply still arrives via key #2.
5. Quota-exhausted test: all keys invalid → user sees `❌ เกิดข้อผิดพลาด: Gemini ทุกคีย์ใช้ไม่ได้` (acceptable v1 UX).

## D. Post-deploy (Render)

- Logs contain `Admin dashboard on` + `Logged in as` within ~2 min of deploy.
- Open service URL: pill shows Online, metrics fill in, log streams.
- With `ADMIN_TOKEN`: switch model via dropdown, add a test key, confirm `/llmstatus` in Discord reflects it.
- Repeat checklist C against the hosted bot.
- Leave running 24h → check for disconnects / sleep (free-tier).

## Regression rule

Any change to `src/handler/`, `src/agent/`, `src/core/llm.py`, or `src/skills/` must re-run checklist C items 1–4 before claiming done.
