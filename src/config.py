"""Central config — mirrors discord-bot-agents/src/config.js.

Single place for env loading. Changing/adding a var requires updating
.env.example + render.yaml + DEPLOY.md together.
"""

import os
import re

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_KEYS", "").split(",") if k.strip()]
if not GEMINI_KEYS and os.getenv("GEMINI_KEY"):  # legacy single-key name
    GEMINI_KEYS = [os.getenv("GEMINI_KEY").strip()]

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

AUTO_REPLY_CHANNEL_IDS = {
    c.strip() for c in os.getenv("AUTO_REPLY_CHANNEL_IDS", "").split(",") if c.strip()
}

HISTORY_LEN = int(os.getenv("HISTORY_LEN", "10"))
BOT_NAME = os.getenv("BOT_NAME", "")

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful Discord AI assistant. Reply concisely in the user's language (default Thai).",
)

# @Bot mention prefix (checked by the handler)
BOT_PREFIX = re.compile(r"<@!?(\d+)>")

# Agent handler tuning
AGENT_COOLDOWN_SEC = 2.0
MAX_ACTIONS = 5

# Default messages
DEFAULT_GREETING = "Hello, I am {botName}. Mention me with a command, e.g. `@Bot list channels`."
NOT_UNDERSTAND = "I am not sure what you meant. Please rephrase your server-management request."
IDENTITY = "I am {botName}, an AI assistant for managing this Discord server."
