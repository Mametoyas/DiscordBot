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

    return list(_local.get((str(channel_id), "*"), []))


def push_history(channel_id: int, role: str, text: str, user_id: int | None = None):
    from src.utils.chat_store import _local

    _local[(str(channel_id), "*")].append({"role": role, "text": text[:2000]})


async def backfill_channel(channel, guild_id=None, limit: int = 50):
    """Pull recent Discord history into the shared channel pool (once per restart)."""
    try:
        messages = [m async for m in channel.history(limit=limit, oldest_first=True)]
    except Exception:  # noqa: BLE001 — e.g. missing Read History permission
        return
    await chat_store.ensure_backfilled(channel.id, guild_id, messages)


async def ask_chat(channel_id: int, user_text: str, user_id: int | None = None,
                 system: str | None = None, guild_id=None) -> str:
    """Group-chat Q&A with CHANNEL-shared memory (DM / auto-channel / /ask).

    Everyone in the channel shares one pool; messages are labeled Name:.
    In guild channels, server-level knowledge (asker's nicknames + matching
    shared facts) is injected so chat answers agree with the agent.
    """
    summary, recent = await chat_store.get_with_summary(channel_id, user_id)
    msgs = recent + [{"role": "user", "text": user_text}]
    sys = system or config.SYSTEM_PROMPT
    if guild_id is not None:
        sys += ("\n\n[Group chat: messages below come from MULTIPLE people, each labeled "
                "Name:. Answer the current speaker, but use anyone's context when relevant.]")
    msgs = recent + [{"role": "user", "text": user_text}]
    sys = system or config.SYSTEM_PROMPT
    try:  # ground the model about its own backbone (stops GPT-4o/Claude hallucinations)
        from src.web.server import MODEL_CHOICES as _CHOICES

        _model = llm.get_client().status()["model"]
        sys += (f"\n\n[Bot internals — authoritative] You run on `{_model}` via the Gemini API. "
                f"Switchable models: {', '.join(_CHOICES)} (via /models, owner/LLMeditor only). "
                "Never name other model families (GPT, Claude, etc.) as yourself.")
    except Exception:  # noqa: BLE001 — grounding is best-effort
        pass
    if summary:
        sys += f"\n\n[Earlier conversation summary — treat as established context]\n{summary}"
    if guild_id is not None:
        try:
            known = await chat_store.aliases_for_member(guild_id, user_id)
            if known:
                sys += f"\n\n[Server record: this user is also known as: {', '.join(known)}]"
            facts = await chat_store.recall_matching(guild_id, user_text, limit=5)
            if facts:
                sys += "\n\n[Server facts]\n" + "\n".join(
                    f"- {f['key']}: {f['content']}" for f in facts)
        except Exception:  # noqa: BLE001 — injection is best-effort
            pass
    reply = await llm.get_client().generate(msgs, system=sys)
    await chat_store.add(channel_id, user_id, "user", user_text, guild_id)
    await chat_store.add(channel_id, user_id, "model", reply, guild_id)
    return reply


async def _mention_system(bot_name: str, message: discord.Message) -> str:
    author = message.author
    base = (
        f"You are {bot_name}, a friendly Discord bot talking directly to a user who mentioned you. "
        "Reply concisely in the user's language (default Thai). Be playful when they are playful — "
        "you may guess, joke, and chat freely like a friend.\n"
        "You REMEMBER this channel across restarts (shared channel memory is automatic) — recall what "
        "ANYONE here said, and never claim you can't remember.\n"
        "Never claim you SAVED something permanently — only explicit remember commands persist "
        "(handled by the server system, not you); if they teach you a nickname, just acknowledge it warmly.\n"
        "Never claim you CANNOT see profiles, mentions, or server info — the server system CAN look anyone up; "
        "if you don't know who someone is, say so plainly and ask for their nickname without inventing limits.\n"
        "You CAN do these things when asked (briefly offer, don't dump the list unprompted): manage "
        "channels/categories/layouts, create/edit/permission roles, give/remove roles, move/mute/deafen "
        "members, kick/ban/timeout, emojis, invites, server info/setup, switch your own AI model (owner only). "
        "If they ask for a server action, say you'll do it once they phrase it as a command."
    )
    # Inject who the author is so LLM never has to guess
    identity = f"\n\nThe user you are talking to RIGHT NOW: username={author.name}, display_name={author.display_name}, id={author.id}."
    if message.guild:
        try:
            aliases = await chat_store.aliases_for_member(message.guild.id, author.id)
            if aliases:
                identity += f" Also known as: {', '.join(aliases)}."
            all_aliases = await chat_store.list_aliases(message.guild.id)
            if all_aliases:
                alias_lines = ", ".join(
                    f"{r['alias']}=<@{r['user_id']}>" for r in all_aliases[:30]
                )
                identity += f"\nServer nickname map (alias=member): {alias_lines}."
        except Exception:  # noqa: BLE001
            pass
    return base + identity


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
                    from src.utils.choice import request_choice
                    from src.utils.confirm import describe_action, request_confirm

                    async def _choice_fn(question: str, options: list[str]) -> tuple:
                        return await request_choice(
                            client, message.channel, message.author.id,
                            question, options, timeout=120.0)

                    async def _confirm_plan(actions: list[dict]) -> bool:
                        lines = [f"{i+1}. {describe_action(a.get('skill', ''), a.get('params') or {})}"
                                 for i, a in enumerate(actions)]
                        return await request_confirm(
                            message.channel, message.author.id,
                            "จะให้ทำตามนี้มั้ย?\n" + "\n".join(lines), timeout=60.0)

                    result = await run_agent(content, message,
                                             confirm_fn=_confirm_plan,
                                             choice_fn=_choice_fn)
                    if result.get("reply") is None:
                        # No server action planned -> chat freely (with memory)
                        # instead of a stiff out-of-scope refusal.
                        bot_name = client.user.display_name if client.user else "Bot"
                        reply = await ask_chat(
                            message.channel.id,
                            f"{message.author.display_name}: {content}",
                            message.author.id,
                            system=await _mention_system(bot_name, message),
                            guild_id=getattr(message.guild, "id", None),
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
            await backfill_channel(message.channel, getattr(message.guild, "id", None))
            reply = await ask_chat(
                message.channel.id, f"{message.author.display_name}: {content}",
                message.author.id,
                guild_id=getattr(message.guild, "id", None),
            )
            await _reply_chunks(message, f"{message.author.mention} {reply}")
        except Exception as e:  # noqa: BLE001 — user-visible fallback
            log.exception("ask failed")
            await message.reply(f"❌ เกิดข้อผิดพลาด: {e}", mention_author=False)
