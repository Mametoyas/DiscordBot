"""Skill registry — mirrors discord-bot-agents/src/skills/index.js.

Each skill: name, description, params dict ('(optional)' marks non-required),
optional required_permissions (discord.py names), optional targets_member
(hierarchy guard in agent/executor.py), async execute(guild, params, message).
"""

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class Skill:
    name: str
    description: str
    params: dict[str, str]
    execute: Callable[..., Awaitable[Any]]
    required_permissions: list[str] = field(default_factory=list)
    targets_member: bool = False
    fetch_raw: Callable[..., Awaitable[Any]] | None = None  # prefetch hook (no-LLM facts)


SKILLS: dict[str, Skill] = {}


def register(skill: Skill) -> Skill:
    SKILLS[skill.name] = skill
    return skill


def definitions() -> list[dict]:
    """Param catalog for the planning prompt (no execute fn)."""
    return [
        {"name": s.name, "description": s.description, "params": s.params}
        for s in SKILLS.values()
    ]


def required_of(skill: Skill) -> list[str]:
    return [
        k for k, v in (skill.params or {}).items()
        if "(optional)" not in v.lower()
    ]


# Import modules so their @register calls run. Order = catalog order.
from . import channels, roles, members, moderation, emojis, invites, server, voice  # noqa: E402,F401
