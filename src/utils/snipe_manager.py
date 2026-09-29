"""Deleted-message log for getSnipe — mirrors utils/snipeManager.js."""

from collections import deque

MAX_SNIPES = 5

_snipes: dict[int, deque] = {}


def add_snipe(channel_id: int, entry: dict):
    q = _snipes.setdefault(channel_id, deque(maxlen=MAX_SNIPES))
    q.appendleft(entry)


def get_snipes(channel_id: int) -> list[dict]:
    return list(_snipes.get(channel_id, []))
