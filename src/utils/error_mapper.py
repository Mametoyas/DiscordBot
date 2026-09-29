"""Map Discord API errors to user-friendly text — mirrors utils/errorMapper.js."""

import discord

CODE_MAP = {
    50013: "I don't have the permissions needed for that — make sure my role is above the target in the hierarchy.",
    50001: "I can't access that channel.",
    10003: "That channel doesn't seem to exist anymore — it might have been deleted.",
    10004: "I couldn't find that server.",
    10007: "That member isn't on this server.",
    10008: "That message is gone — it might have been deleted.",
    10011: "I couldn't find that role.",
    10014: "I couldn't find that emoji.",
    30008: "This server has hit the max emoji limit already.",
    429: "Discord's API is rate-limiting us right now — give it a moment and try again.",
    50035: "The input I sent was invalid — something didn't match what Discord expects.",
}


def map_discord_error(err: Exception) -> str:
    if err is None:
        return "Something went wrong, but I'm not sure what."
    if isinstance(err, ValueError):
        return str(err) or "Something went wrong."  # skill's own user-friendly message
    code = getattr(err, "code", 0) or getattr(err, "status", 0) or 0
    if code in CODE_MAP:
        return CODE_MAP[code]
    text = str(err) or ""
    if "Missing Permissions" in text:
        return "I'm missing the permissions I need to do that."
    if "Privilege is too low" in text:
        return "My role isn't high enough to manage that target."
    if isinstance(err, discord.Forbidden):
        return "Discord refused that action (permissions or hierarchy)."
    if isinstance(err, discord.HTTPException):
        return "Discord returned an error — try again, or check permissions."
    return (text[:300] if text else "I couldn't reach Discord's servers — there might be a connection issue.")
