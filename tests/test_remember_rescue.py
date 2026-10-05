"""rememberFact rescues planner gaps: '?' key + dropped roster."""

import unittest

from src.skills.memory import _infer_roster_key


class TestInferRosterKey(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(_infer_roster_key("ตี้พับจีมีสมาชิกดังนี้ @a @b"), "ตี้พับจี")

    def test_spaced(self):
        self.assertEqual(_infer_roster_key("ปกติ ตี้ PUBG มี @a"), "ตี้PUBG")

    def test_team_word(self):
        self.assertEqual(_infer_roster_key("ทีมวาโลคือ @a", ), "ทีมวาโล")

    def test_no_subject(self):
        self.assertIsNone(_infer_roster_key("จำไว้ว่าฟ้าสวย"))


if __name__ == "__main__":
    unittest.main()
