"""Executor fills a dropped memberId from the message's single mention."""

import unittest

from src.agent import executor
from src.skills import SKILLS, Skill


class FakePerms:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        return False


class FakeUser:
    def __init__(self, id, bot=False):
        self.id = id
        self.bot = bot


class FakeGuild:
    def __init__(self):
        self.owner_id = 1
        self.me = FakeUser(2)


class FakeAuthor(FakeUser):
    guild_permissions = FakePerms()


class FakeMessage:
    def __init__(self, mentions):
        self.mentions = mentions
        self.author = FakeAuthor(3)
        self.guild = FakeGuild()


class TestAutofill(unittest.IsolatedAsyncioTestCase):
    async def test_single_mention_fills_member_id(self):
        seen = {}

        async def _exec(guild, params, message):
            seen.update(params)
            return True

        SKILLS["__test_probe__"] = Skill(
            name="__test_probe__", description="probe",
            params={"memberId": "string - who.", "note": "string (optional) - x."},
            execute=_exec)
        try:
            msg = FakeMessage([FakeUser(2), FakeUser(777)])
            res = await executor.execute(
                [{"skill": "__test_probe__", "params": {}}], msg)
        finally:
            SKILLS.pop("__test_probe__", None)
        self.assertEqual(res[0]["status"], "success")
        self.assertEqual(seen.get("memberId"), "777")

    async def test_no_mention_still_missing(self):
        async def _exec(guild, params, message):
            return True

        SKILLS["__test_probe2__"] = Skill(
            name="__test_probe2__", description="probe",
            params={"memberId": "string - who."},
            execute=_exec)
        try:
            res = await executor.execute(
                [{"skill": "__test_probe2__", "params": {}}], FakeMessage([]))
        finally:
            SKILLS.pop("__test_probe2__", None)
        self.assertEqual(res[0]["status"], "failed")
        self.assertIn("memberId", res[0]["error"])


if __name__ == "__main__":
    unittest.main()
