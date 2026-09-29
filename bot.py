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

if config.GEMINI_KEYS:
    llm.configure(config.GEMINI_KEYS, config.GEMINI_MODEL, config.SYSTEM_PROMPT)
    gemini = llm.get_client()
else:
    gemini = None

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True  # music skills need to see voice channels

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


async def _connect_lavalink():
    """Connect wavelink pool once (skipped if unconfigured)."""
    import wavelink

    if not config.LAVALINK_HOST or not config.LAVALINK_PASSWORD:
        log.warning("LAVALINK_HOST/PASSWORD not set — voice skills disabled")
        return
    if getattr(wavelink.Pool, "nodes", None):
        return
    try:
        await wavelink.Pool.connect(
            client=client,
            nodes=[wavelink.Node(uri=config.LAVALINK_HOST, password=config.LAVALINK_PASSWORD)],
        )
        log.info(f"Lavalink connected ({config.LAVALINK_HOST})")
    except Exception as e:
        log.error(f"Lavalink connect failed: {e}")


@client.event
async def on_ready():
    log.info(f"Logged in as {client.user}")
    try:
        await tree.sync()
        log.info("Slash commands synced (/ask)")
    except Exception as e:
        log.error(f"sync commands ล้มเหลว: {e}")
    await _connect_lavalink()


@client.event
async def on_wavelink_node_ready(payload):
    log.info(f"Lavalink node ready ({getattr(payload.node, 'identifier', '?')})")


@client.event
async def on_wavelink_track_end(payload):
    """Autoplay is OFF — advance the queue only on natural finish."""
    try:
        if getattr(payload, "reason", "") != "finished":
            return
        player = payload.player
        if player is None:
            return
        nxt = player.queue.get()
        await player.play(nxt)
    except Exception:
        pass  # empty queue or transient error — stay silent


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


async def _play_autocomplete(interaction: discord.Interaction, current: str):
    from src.skills import voice as _v

    try:
        pairs = await _v.search_choices(current)
    except Exception:
        pairs = []
    return [app_commands.Choice(name=label, value=value) for label, value in pairs][:25]


@tree.command(name="play", description="เปิดเพลง (พิมพ์ชื่อแล้วเลือกจาก suggest)")
@app_commands.describe(query="ชื่อเพลงหรือลิงก์ YouTube")
@app_commands.autocomplete(query=_play_autocomplete)
async def play_cmd(interaction: discord.Interaction, query: str):
    from src.skills import voice as _v

    if interaction.guild is None:
        await interaction.response.send_message("❌ ใช้ใน server เท่านั้น", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        result = await _v.do_play(interaction.guild, interaction.user, query)
        await interaction.followup.send(str(result))
    except Exception as e:
        await interaction.followup.send(f"❌ {e}")


@tree.command(name="skip", description="ข้ามไปเพลงถัดไป")
async def skip_cmd(interaction: discord.Interaction):
    from src.skills import voice as _v

    if interaction.guild is None:
        await interaction.response.send_message("❌ ใช้ใน server เท่านั้น", ephemeral=True)
        return
    try:
        await interaction.response.send_message(str(await _v.do_skip(interaction.guild)))
    except Exception as e:
        await interaction.response.send_message(f"❌ {e}", ephemeral=True)


@tree.command(name="stop", description="หยุดเพลง + ล้างคิว")
async def stop_cmd(interaction: discord.Interaction):
    from src.skills import voice as _v

    if interaction.guild is None:
        await interaction.response.send_message("❌ ใช้ใน server เท่านั้น", ephemeral=True)
        return
    await interaction.response.send_message(str(await _v.do_stop(interaction.guild)))


@tree.command(name="queue", description="ดูคิวเพลง")
async def queue_cmd(interaction: discord.Interaction):
    from src.skills import voice as _v

    if interaction.guild is None:
        await interaction.response.send_message("❌ ใช้ใน server เท่านั้น", ephemeral=True)
        return
    await interaction.response.send_message(str(await _v.do_queue(interaction.guild)))


@tree.command(name="leave", description="ให้บอทออกจากห้องเสียง")
async def leave_cmd(interaction: discord.Interaction):
    from src.skills import voice as _v

    if interaction.guild is None:
        await interaction.response.send_message("❌ ใช้ใน server เท่านั้น", ephemeral=True)
        return
    await interaction.response.send_message(str(await _v.do_leave(interaction.guild)))


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
