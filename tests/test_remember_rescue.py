"""rememberFact rescues planner gaps: '?' key + dropped roster."""

import unittest
from unittest.mock import AsyncMock, patch

from src.skills import memory as mem_mod
from src.skills.memory import _infer_roster_key, _remember


class TestInferRosterKey(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(_infer_roster_key("ตี้พับจีมีสมาชิกดังนี้ @a @b"), "ตี้พับจี")

    def test_spaced(self):
        self.assertEqual(_infer_roster_key("ปกติ ตี้ PUBG มี @a"), "ตี้PUBG")

    def test_team_word(self):
        self.assertEqual(_infer_roster_key("ทีมวาโลคือ @a", ), "ทีมวาโล")

    def test_no_subject(self):
        self.assertIsNone(_infer_roster_key("จำไว้ว่าฟ้าสวย"))


class FakeUser:
    def __init__(self, id, display_name, bot=False):
        self.id = id
        self.display_name = display_name
        self.mention = f"<@{id}>"
        self.bot = bot


class FakeMessage:
    def __init__(self, content, mentions):
        self.content = content
        self.mentions = mentions
        self.author = FakeUser(999, "Tester")
        self.guild = None


class TestRememberRescue(unittest.IsolatedAsyncioTestCase):
    async def test_missing_key_and_content_rescued(self):
        msg = FakeMessage(
            "ตี้พับจีมีสมาชิกดังนี้ <@1> <@2>",
            [FakeUser(1, "A"), FakeUser(2, "B")])
        with patch.object(mem_mod.store, "remember_fact",
                          new=AsyncMock()) as mock_save:
            out = await _remember(FakeGuild(), {}, msg)
        self.assertIn("ตี้พับจี", out)
        _, key, content = mock_save.call_args[0][:3]
        self.assertEqual(key, "ตี้พับจี")
        self.assertIn("A (<@1>)", content)

    async def test_question_mark_key_rescued(self):
        msg = FakeMessage("ตี้พับจีมีสมาชิกดังนี้ <@1>", [FakeUser(1, "A")])
        with patch.object(mem_mod.store, "remember_fact",
                          new=AsyncMock()) as mock_save:
            await _remember(FakeGuild(), {"key": "?"}, msg)
        self.assertEqual(mock_save.call_args[0][1], "ตี้พับจี")

    async def test_unrecoverable_raises(self):
        msg = FakeMessage("จำไว้ว่าฟ้าสวย", [])
        with self.assertRaises(ValueError):
            await _remember(FakeGuild(), {}, msg)


class FakeGuild:
    id = 123


if __name__ == "__main__":
    unittest.main()

