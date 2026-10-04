"""Phase 2: EXECUTE — port of discord-bot-agents/src/agent/executor.js."""

import discord

from src.skills import SKILLS, required_of
from src.utils.confirm import describe_action, request_confirm
from src.utils.error_mapper import map_discord_error as map_error
from src.utils.fuzzy_match import find_member


def _hierarchy_ok(guild: discord.Guild, requester: discord.Member, target: discord.Member) -> str | None:
    """Return error string if the moderation target is protected, else None."""
    bot_me = guild.me
    if target.id == guild.owner_id:
        return f"I can't moderate {target.display_name} — they own this server."
    if target.id == bot_me.id:
        return "I can't moderate myself."
    if bot_me.top_role.position <= target.top_role.position:
        return f"I can't moderate {target.display_name} — my role isn't high enough."
    if requester.id != guild.owner_id and requester.top_role.position <= target.top_role.position:
        return f"You can't moderate {target.display_name} — their role matches or beats yours."
    return None


async def execute(actions: list[dict], message, pre_confirmed: bool = False) -> list[dict]:
    guild = message.guild
    results: list[dict] = []
    for action in actions:
        name = action.get("skill", "")
        params = action.get("params") or {}
        skill = SKILLS.get(name)
        if not skill:
            results.append({"skill": name, "status": "failed", "error": "Unknown skill"})
            continue

        missing = [k for k in required_of(skill) if params.get(k) in (None, "")]
        if missing:
            results.append({
                "skill": name, "status": "failed",
                "error": f"Missing required params: {', '.join(missing)}",
            })
            continue

        if skill.required_permissions:
            bot_missing = [p for p in skill.required_permissions
                           if not getattr(guild.me.guild_permissions, p, False)]
            if bot_missing:
                results.append({
                    "skill": name, "status": "failed",
                    "error": f"I am missing permissions: {', '.join(bot_missing)}",
                })
                continue
            if message.author.id != guild.owner_id and not message.author.guild_permissions.administrator:
                user_missing = [p for p in skill.required_permissions
                                if not getattr(message.author.guild_permissions, p, False)]
                if user_missing:
                    results.append({
                        "skill": name, "status": "failed",
                        "error": f"You are missing permissions: {', '.join(user_missing)}",
                    })
                    continue

        if skill.targets_member and params.get("memberId"):
            target = await find_member(guild, params["memberId"])
            if target:
                err = _hierarchy_ok(guild, message.author, target)
                if err:
                    results.append({"skill": name, "status": "failed", "error": err})
                    continue

        if skill.needs_confirm and not pre_confirmed:
            try:
                ok = await request_confirm(
                    message.channel, message.author.id,
                    describe_action(name, params), timeout=60.0)
            except Exception as e:  # noqa: BLE001 — no prompt possible, stay safe
                results.append({"skill": name, "status": "failed",
                                "error": f"Confirmation prompt failed, action cancelled: {e}"})
                continue
            if not ok:
                results.append({"skill": name, "status": "failed",
                                "error": "Cancelled — the action was not confirmed."})
                continue

        try:
            out = await skill.execute(guild, params, message)
            results.append({"skill": name, "status": "success", "result": out})
        except Exception as e:  # noqa: BLE001 — mapped to friendly text below
            results.append({"skill": name, "status": "failed", "error": map_error(e)})
    return results
