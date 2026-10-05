"""Post-process outgoing replies: turn `@DisplayName` text into real `<@id>` pings.

LLMs often write "@Mametoyas" as plain text, which Discord does NOT ping.
This pass resolves member names against the guild so every reply actually notifies.
Existing `<@..>` / `<#..>` / `<@&..>` / emoji syntax and code blocks are untouched.
"""

import re

_PROTECT_RE = re.compile(r"<(?:#|@!?|@&|a?:\w+:)(\d+)>")
_CODE_SPLIT_RE = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)


def apply_mentions(text: str, guild) -> str:
    if not text or guild is None:
        return text
    parts = _CODE_SPLIT_RE.split(text)
    for i in range(0, len(parts), 2):  # even indices = outside code
        parts[i] = _resolve_plain(parts[i], guild)
    return "".join(parts)


def _resolve_plain(segment: str, guild) -> str:
    if "@" not in segment:
        return segment
    # longest names first so "พี่โขงสุดหล่อกว่าพี่เต้ย" wins over "โขง"
    members = sorted(guild.members,
                     key=lambda m: len(m.display_name), reverse=True)
    # remember which IDs are already properly mentioned
    already = set(_PROTECT_RE.findall(segment))
    for m in members:
        if str(m.id) in already:
            continue
        for name in (m.display_name, m.name):
            if not name or f"@{name}" not in segment:
                continue
            segment = re.sub(
                r"(?<!\w)@" + re.escape(name) + r"(?!\w)",
                f"<@{m.id}>", segment)
            already.add(str(m.id))
            break
    return segment
