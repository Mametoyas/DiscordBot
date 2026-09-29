"""Extract JSON from LLM output — mirrors utils/jsonHelper.js.

Handles fences, preamble text, trailing commas, smart quotes, and raw
control chars inside strings; falls back to loose field extraction.
"""

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_FIELD_RE_CACHE: dict[str, re.Pattern] = {}


def _field_re(field: str) -> re.Pattern:
    if field not in _FIELD_RE_CACHE:
        _FIELD_RE_CACHE[field] = re.compile(rf'"{field}"\s*:\s*"((?:\\.|[^"\\])*)"', re.DOTALL)
    return _FIELD_RE_CACHE[field]


def _slice_balanced(text: str, start: int) -> str | None:
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if in_str:
            if ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _repair_commas(s: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", s)


def _repair_controls(s: str) -> str:
    out, in_str, esc = [], False, False
    for ch in s:
        if esc:
            out.append(ch)
            esc = False
            continue
        if in_str:
            if ch == "\\":
                out.append(ch)
                esc = True
                continue
            if ch == '"':
                out.append(ch)
                in_str = False
                continue
            if ch == "\n":
                out.append("\\n")
                continue
            if ch == "\r":
                out.append("\\r")
                continue
            if ch == "\t":
                out.append("\\t")
                continue
            if ord(ch) < 0x20:
                out.append("\\u%04x" % ord(ch))
                continue
            out.append(ch)
            continue
        if ch == '"':
            in_str = True
        out.append(ch)
    return "".join(out)


def _smart_quotes(s: str) -> str:
    return (s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'"))


def _try_parse(s: str) -> dict | None:
    for attempt in (s, _repair_commas(s), _repair_controls(s),
                    _repair_commas(_repair_controls(s)),
                    _smart_quotes(s), _repair_commas(_repair_controls(_smart_quotes(s)))):
        try:
            parsed = json.loads(attempt)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def _loose_fields(text: str) -> dict | None:
    m = _field_re("reply").search(text)
    if not m:
        return None
    try:
        reply = json.loads('"' + m.group(1) + '"')
    except json.JSONDecodeError:
        reply = m.group(1)

    def _field(name: str, default=None):
        mm = _field_re(name).search(text)
        if not mm:
            return default
        try:
            return json.loads('"' + mm.group(1) + '"')
        except json.JSONDecodeError:
            return mm.group(1)

    return {
        "reply": reply,
        "reasoning": _field("reasoning", ""),
        "replyFormat": _field("replyFormat", "text"),
    }


def extract_json(text) -> dict | None:
    if text is None or isinstance(text, dict):
        return text
    if not isinstance(text, str):
        return None
    trimmed = text.strip()
    if not trimmed:
        return None
    candidates = [trimmed]
    fence = _FENCE_RE.search(trimmed)
    if fence:
        candidates.append(fence.group(1).strip())
    brace = trimmed.find("{")
    if brace != -1:
        balanced = _slice_balanced(trimmed, brace)
        if balanced:
            candidates.append(balanced)
    for cand in candidates:
        parsed = _try_parse(cand)
        if parsed:
            return parsed
    return _loose_fields(trimmed)
