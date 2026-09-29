"""Thin entry point — mirrors discord-bot-agents/src/index.js.

Keeps `python bot.py` (Procfile / render.yaml) working. All logic lives in src/:
  src/config.py   env loading
  src/core/llm.py Gemini multi-key client
  src/agent/      plan → execute → summarize
  src/skills/     34 Discord skills
  src/handler/    Discord message adapter
  src/utils/      fuzzy_match / error_mapper / json_helper / snipe_manager
"""

import logging

import discord
from discord import app_commands

from src import config
from src.core import llm
from src.handler import message_handler
from src.utils import snipe_manager
from src.web import server as webadmin

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gemini-bot")
# httpx logs full request URLs at INFO — and our URLs contain ?key=... — silence it
logging.getLogger("httpx").setLevel(logging.WARNING)

if config.GEMINI_KEYS:
    llm.configure(config.GEMINI_KEYS, config.GEMINI_MODEL, config.SYSTEM_PROMPT)
    gemini = llm.get_client()
else:
    gemini = None

_tok = config.DISCORD_TOKEN
log.info(f"Token fingerprint: {(_tok[:6] + '…') if _tok else '(empty)'} len={len(_tok)}")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    log.info(f"Logged in as {client.user}")
    try:
        await tree.sync()
        log.info("Slash commands synced (/ask)")
    except Exception as e:
        log.error(f"sync commands ล้มเหลว: {e}")


@tree.command(name="ask", description="ถาม AI (Gemini)")
@app_commands.describe(question="คำถามของคุณ")
async def ask_cmd(interaction: discord.Interaction, question: str):
    await interaction.response.defer(thinking=True)
    try:
        reply = await message_handler.ask_chat(interaction.channel_id, question)
        for part in message_handler.chunk(reply):
            await interaction.followup.send(part)
    except Exception as e:
        await interaction.followup.send(f"❌ เกิดข้อผิดพลาด: {e}")


@tree.command(name="help", description="วิธีใช้บอททั้งหมด")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**💬 คุย/ถาม** — `/ask คำถาม` · DM · หรือพิมพ์ในช่อง auto-reply\n"
        "**🤖 สั่งจัดการ server** — `@Bot ...` เช่น `@Bot สร้างยศ VIP สีแดงให้ @ploy`, `@Bot timeout @เกรียน 10 นาที`, `@Bot list channels`\n"
        "**📄 ลิสต์ยาวๆ** — มีปุ่ม ◀ ▶ เปลี่ยนหน้า (กดได้เฉพาะคนสั่ง)\n"
        "**🧠 เจ้าของ server** — `/model` · `/addkey` · `/llmstatus`",
        ephemeral=True,
    )


def _is_owner(interaction: discord.Interaction) -> bool:
    return interaction.guild is not None and interaction.user.id == interaction.guild.owner_id


@tree.command(name="model", description="ดู/เปลี่ยนโมเดล Gemini (เจ้าของ server เท่านั้น)")
@app_commands.describe(name="ชื่อโมเดลใหม่ เช่น gemini-2.5-flash (เว้นว่าง = ดูค่าปัจจุบัน)")
async def model_cmd(interaction: discord.Interaction, name: str | None = None):
    if not _is_owner(interaction):
        await interaction.response.send_message("❌ เฉพาะเจ้าของ server", ephemeral=True)
        return
    if not name:
        s = llm.get_client().status()
        await interaction.response.send_message(
            f"🧠 model: `{s['model']}` | keys: {s['keys']} (พักอยู่ {s['cooling_down']})",
            ephemeral=True,
        )
        return
    llm.get_client().set_model(name)
    await interaction.response.send_message(f"✅ เปลี่ยน backbone เป็น `{name.strip()}` แล้ว (มีผลทันที)", ephemeral=True)


@tree.command(name="addkey", description="เพิ่ม Gemini API key ตอนรัน (เจ้าของ server เท่านั้น)")
@app_commands.describe(key="API key ใหม่ (คั่น comma ได้หลายดอก)")
async def addkey_cmd(interaction: discord.Interaction, key: str):
    if not _is_owner(interaction):
        await interaction.response.send_message("❌ เฉพาะเจ้าของ server", ephemeral=True)
        return
    added = llm.get_client().add_keys(key.split(","))
    s = llm.get_client().status()
    await interaction.response.send_message(
        f"✅ เพิ่ม {added} key (รวม {s['keys']} keys)" if added else "⚠️ key นี้มีอยู่แล้ว",
        ephemeral=True,
    )


@tree.command(name="llmstatus", description="ดูสถานะ LLM (เจ้าของ server เท่านั้น)")
async def llmstatus_cmd(interaction: discord.Interaction):
    if not _is_owner(interaction):
        await interaction.response.send_message("❌ เฉพาะเจ้าของ server", ephemeral=True)
        return
    s = llm.get_client().status()
    await interaction.response.send_message(
        f"🧠 model: `{s['model']}`\n🔑 keys: {s['keys']} (พักอยู่ {s['cooling_down']})",
        ephemeral=True,
    )


@client.event
async def on_message_delete(message: discord.Message):
    if message.author and message.author.bot:
        return
    if not message.guild:
        return
    snipe_manager.add_snipe(message.channel.id, {
        "content": message.content,
        "author": str(message.author),
        "at": message.created_at,
    })


@client.event
async def on_message(message: discord.Message):
    await message_handler.handle_message(message, client)


if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        raise SystemExit("❌ ไม่เจอ DISCORD_TOKEN — ตั้งค่าใน .env หรือ Environment Variables")
    if gemini is None:
        raise SystemExit("❌ ไม่เจอ GEMINI_KEYS — ใส่คีย์อย่างน้อย 1 ตัว")
    import os as _os

    webadmin.start(client, int(_os.getenv("PORT", "8080")), _os.getenv("ADMIN_TOKEN", ""))
    client.run(config.DISCORD_TOKEN)
