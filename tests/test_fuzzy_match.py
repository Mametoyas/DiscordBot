"""Name search: exact username/nick + Thai honorific stripping."""

import asyncio
import unittest

import discord  # noqa: F401 (real exceptions used by fuzzy_match)

from src.utils import fuzzy_match


class FakeMember:
    def __init__(self, name, nick=None):
        self.name = name
        self.nick = nick
        self.display_name = nick or name


class FakeGuild:
    def __init__(self, members):
        self.members = members

    def get_member(self, uid):
        return None

    async def fetch_member(self, uid):
        raise ValueError("nope")

    async def query_members(self, query=None, limit=1):
        return []


def find(q):
    guild = FakeGuild([FakeMember("thunder"), FakeMember("nova_x", "Nova")])
    return asyncio.run(fuzzy_match.find_member(guild, q))


class TestFindMember(unittest.TestCase):
    def test_username(self):
        self.assertIsNotNone(find("thunder"))

    def test_nickname(self):
        self.assertIsNotNone(find("Nova"))

    def test_thai_prefix_stripped(self):
        self.assertIsNotNone(find("ไอ้Nova"))

    def test_thai_prefix_username(self):
        self.assertIsNotNone(find("ไอ้ thunder"))

    def test_missing_returns_none(self):
        self.assertIsNone(find("ใครก็ไม่รู้xyz"))


if __name__ == "__main__":
    unittest.main()
