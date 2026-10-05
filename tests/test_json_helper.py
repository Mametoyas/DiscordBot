"""Planner JSON extraction must survive reasoning preamble and fences."""

import unittest

from src.utils.json_helper import extract_json


class TestExtractJson(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(
            extract_json('{"reasoning":"r","actions":[]}'),
            {"reasoning": "r", "actions": []})

    def test_fence(self):
        self.assertEqual(
            extract_json('```json\n{"a":1}\n```')["a"], 1)

    def test_reasoning_preamble(self):
        raw = ('The user wants a role. I will create it.\n'
               '{"reasoning":"create role","actions":[{"skill":"createRole",'
               '"params":{"name":"Gamer"}}]}')
        parsed = extract_json(raw)
        self.assertEqual(parsed["actions"][0]["skill"], "createRole")

    def test_trailing_comma(self):
        self.assertEqual(extract_json('{"a":1,}')["a"], 1)

    def test_garbage_returns_none_or_loose(self):
        self.assertIsNone(extract_json("just chatting, no json"))


if __name__ == "__main__":
    unittest.main()
