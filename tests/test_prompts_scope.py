"""Regression: every `-> skill` referenced in the planner SCOPE must exist.

Catches getMemberInfo-class ghosts (prompt names a skill that was never
registered -> planner emits it -> executor fails 'Unknown skill').
"""

import re
import unittest

from src.skills import SKILLS
from src.agent import prompts


class TestScopeSkillsExist(unittest.TestCase):
    def test_all_scope_targets_registered(self):
        with open(prompts.__file__, encoding="utf-8") as f:
            src = f.read()
        refs = set(re.findall(r"->\s*(\w+)", src))
        # filter plain-English words, keep CamelCase skill-like tokens
        candidates = {r for r in refs if re.search(r"[a-z][A-Z]", r)}
        missing = sorted(c for c in candidates if c not in SKILLS)
        self.assertEqual(missing, [], f"SCOPE names unregistered skills: {missing}")


if __name__ == "__main__":
    unittest.main()
