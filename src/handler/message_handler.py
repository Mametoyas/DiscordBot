"""Discord adapter — mirrors discord-bot-agents/src/handler/messageHandler.js.

Owns: mention parsing, per-user cooldown, empty-mention greeting (0 LLM),
agent path (guild mentions), chat path (DM / auto-channel, per-channel
history), and reply rendering (button paginator for long lists).
"""

import logging
import time
from collections import defaultdict, deque

import discord

from src import config
from src.agent import run as run_agent
from src.core import llm
from .paginator import reply_paginated, split_pages

log = logging.getLogger("gemini-bot")

_histories: dict[int, deque] = defaultdict(lambda: deque(maxlen=config.HISTORY_LEN * 2))
_agent_cooldowns: dict[int, float] = {}


def chunk(text: str, limit: int = 1900) -> list[str]:
    """Kept for /ask followups; message replies use split_pages + buttons."""
    return split_pages(text, limit)


def get_history(channel_id: int) -> list[dict]:
    return list(_histories[channel_id])


def push_history(channel_id: int, role: str, text: str):
    _histories[channel_id].append({"role": role, "text": text[:2000]})


async def ask_chat(channel_id: int, user_text: str) -> str:
    """Chat Q&A with per-channel memory (DM / auto-channel / /ask)."""
    msgs = get_history(channel_id) + [{"role": "user", "text": user_text}]
    reply = await llm.get_client().generate(msgs)
    push_history(channel_id, "user", user_text)
    push_history(channel_id, "model", reply)
    return reply


async def _reply_chunks(message: discord.Message, text: str):
    await reply_paginated(message, text)


async def handle_message(message: discord.Message, client: discord.Client):
    if message.author.bot:
        return

    content = message.content.strip()
    if not content:
        return

    m = config.BOT_PREFIX.search(content)
    is_mention = client.user in message.mentions or (m and m.group(1) == str(client.user.id))
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_auto_channel = str(message.channel.id) in config.AUTO_REPLY_CHANNEL_IDS

    if is_mention:
        content = content.replace(f"<@{client.user.id}>", "").replace(
            f"<@!{client.user.id}>", "").strip()

        if not content:  # bare mention — greet, no LLM call
            name = client.user.display_name if client.user else config.BOT_NAME or "Bot"
            await message.reply(
                config.DEFAULT_GREETING.format(botName=name), mention_author=False)
            return

        if message.guild is not None:  # server → agent (plan → execute → summarize)
            now = time.monotonic()
            if now - _agent_cooldowns.get(message.author.id, 0) < config.AGENT_COOLDOWN_SEC:
                return
            _agent_cooldowns[message.author.id] = now
            async with message.channel.typing():
                try:
                    result = await run_agent(content, message)
                    await _reply_chunks(message, result["reply"])
                except Exception as e:  # noqa: BLE001 — user-visible fallback
                    log.exception("agent failed")
                    await message.reply(f"❌ เกิดข้อผิดพลาด: {e}", mention_author=False)
            return
        # Mention in DM falls through to chat below (markup already stripped).

    if not (is_dm or is_auto_channel):
        return

    async with message.channel.typing():
        try:
            reply = await ask_chat(message.channel.id, f"{message.author.display_name}: {content}")
            await _reply_chunks(message, f"{message.author.mention} {reply}")
        except Exception as e:  # noqa: BLE001 — user-visible fallback
            log.exception("ask failed")
            await message.reply(f"❌ เกิดข้อผิดพลาด: {e}", mention_author=False)
