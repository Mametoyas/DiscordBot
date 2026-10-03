"""Discord adapter — mirrors discord-bot-agents/src/handler/messageHandler.js.

Owns: mention parsing, per-user cooldown, empty-mention greeting (0 LLM),
agent path (guild mentions), chat path (DM / auto-channel, per-user
memory via chat_store), and reply rendering (button paginator for long lists).
"""

import logging
import time

import discord

from src import config
from src.agent import run as run_agent
from src.core import llm
from src.utils.chat_store import store as chat_store
from .paginator import reply_paginated, split_pages

log = logging.getLogger("gemini-bot")

_agent_cooldowns: dict[int, float] = {}


def chunk(text: str, limit: int = 1900) -> list[str]:
    """Kept for /ask followups; message replies use split_pages + buttons."""
    return split_pages(text, limit)


def get_history(channel_id: int, user_id: int | None = None) -> list[dict]:
    """Sync peek at the local fallback copy (Supabase reads are async)."""
    from src.utils.chat_store import _local

    if user_id is None:
        out: list[dict] = []
        for (ch, _u), dq in _local.items():
            if str(ch) == str(channel_id):
                out.extend(dq)
        return out
    return list(_local.get((str(channel_id), str(user_id)), []))


def push_history(channel_id: int, role: str, text: str, user_id: int | None = None):
    from src.utils.chat_store import _local

    _local[(str(channel_id), str(user_id))].append({"role": role, "text": text[:2000]})


async def ask_chat(channel_id: int, user_text: str, user_id: int | None = None,
                 system: str | None = None) -> str:
    """Chat Q&A with per-user-in-channel memory (DM / auto-channel / /ask)."""
    msgs = await chat_store.get(channel_id, user_id) + [{"role": "user", "text": user_text}]
    reply = await llm.get_client().generate(msgs, system=system or config.SYSTEM_PROMPT)
    guild_id = None
    await chat_store.add(channel_id, user_id, "user", user_text, guild_id)
    await chat_store.add(channel_id, user_id, "model", reply, guild_id)
    return reply


def _mention_system(bot_name: str) -> str:
    return (
        f"You are {bot_name}, a friendly Discord bot talking directly to a user who mentioned you. "
        "Reply concisely in the user's language (default Thai). Be playful when they are playful — "
        "you may guess, joke, and chat freely like a friend.\n"
        "You REMEMBER this user across restarts (per-user memory is automatic) — recall preferences "
        "they told you, and never claim you can't remember.\n"
        "Never claim you SAVED something permanently — only explicit remember commands persist "
        "(handled by the server system, not you); if they teach you a nickname, just acknowledge it warmly.\n"
        "You CAN do these things when asked (briefly offer, don't dump the list unprompted): manage "
        "channels/categories/layouts, create/edit/permission roles, give/remove roles, move/mute/deafen "
        "members, kick/ban/timeout, emojis, invites, server info/setup, switch your own AI model (owner only). "
        "If they ask for a server action, say you'll do it once they phrase it as a command."
    )


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
                    if result.get("reply") is None:
                        # No server action planned -> chat freely (with memory)
                        # instead of a stiff out-of-scope refusal.
                        bot_name = client.user.display_name if client.user else "Bot"
                        reply = await ask_chat(
                            message.channel.id,
                            f"{message.author.display_name}: {content}",
                            message.author.id,
                            system=_mention_system(bot_name),
                        )
                        await _reply_chunks(message, reply)
                    else:
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
            reply = await ask_chat(
                message.channel.id, f"{message.author.display_name}: {content}",
                message.author.id,
            )
            await _reply_chunks(message, f"{message.author.mention} {reply}")
        except Exception as e:  # noqa: BLE001 — user-visible fallback
            log.exception("ask failed")
            await message.reply(f"❌ เกิดข้อผิดพลาด: {e}", mention_author=False)
