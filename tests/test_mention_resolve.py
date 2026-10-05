"""Outgoing @Name text must become real <@id> pings. Run: python -m unittest discover tests."""

import unittest

from src.utils.mention_resolve import apply_mentions


class FakeMember:
    def __init__(self, id, name, display_name=None):
        self.id = id
        self.name = name
        self.display_name = display_name or name


class FakeGuild:
    def __init__(self, members):
        self.members = members


class TestApplyMentions(unittest.TestCase):
    def setUp(self):
        self.guild = FakeGuild([
            FakeMember(111, "mametoyas", "Mametoyas"),
            FakeMember(222, "kho", "พี่โขงสุดหล่อกว่าพี่เต้ย"),
        ])

    def test_plain_name_becomes_ping(self):
        out = apply_mentions("เต้ยยย @Mametoyas อยากเล่นอะไร", self.guild)
        self.assertIn("<@111>", out)
        self.assertNotIn("@Mametoyas", out)

    def test_longest_name_wins(self):
        out = apply_mentions("เรียก @พี่โขงสุดหล่อกว่าพี่เต้ย มาหน่อย", self.guild)
        self.assertIn("<@222>", out)

    def test_existing_mention_untouched(self):
        out = apply_mentions("hi <@111> and @Mametoyas", self.guild)
        self.assertEqual(out.count("<@111>"), 2)  # one kept, one converted

    def test_code_block_untouched(self):
        out = apply_mentions("run `@Mametoyas` now", self.guild)
        self.assertIn("`@Mametoyas`", out)

    def test_unknown_name_untouched(self):
        out = apply_mentions("hello @NobodyHere", self.guild)
        self.assertIn("@NobodyHere", out)

    def test_no_guild_passthrough(self):
        self.assertEqual(apply_mentions("@Mametoyas hi", None), "@Mametoyas hi")


if __name__ == "__main__":
    unittest.main()
