"""ENHANCE.md Phase 7: rate-limit + quota-message tests (no network)."""

import unittest

from src.core.llm import QUOTA_EXHAUSTED_MSG
from src.utils.rate_limit import RateLimiter


class TestRateLimit(unittest.TestCase):
    def test_chat_cooldown(self):
        r = RateLimiter(chat_per_min=100, agent_per_min=100, guild_per_min=1000,
                        chat_cooldown_sec=5.0)
        ok, _ = r.check_chat(1, now=100.0)
        self.assertTrue(ok)
        ok, reason = r.check_chat(1, now=101.0)
        self.assertFalse(ok)
        self.assertEqual(reason, "cooldown")

    def test_chat_burst_cap(self):
        r = RateLimiter(chat_per_min=2, agent_per_min=100, guild_per_min=1000,
                        chat_cooldown_sec=0)
        self.assertTrue(r.check_chat(7, now=0.0)[0])
        self.assertTrue(r.check_chat(7, now=1.0)[0])
        self.assertFalse(r.check_chat(7, now=2.0)[0])

    def test_flood_recovers_after_window(self):
        r = RateLimiter(chat_per_min=2, agent_per_min=100, guild_per_min=1000,
                        chat_cooldown_sec=0)
        r.check_chat(9, now=0.0)
        r.check_chat(9, now=1.0)
        self.assertFalse(r.check_chat(9, now=2.0)[0])
        self.assertTrue(r.check_chat(9, now=61.0)[0])

    def test_agent_cap(self):
        r = RateLimiter(chat_per_min=100, agent_per_min=1, guild_per_min=1000,
                        chat_cooldown_sec=0)
        self.assertTrue(r.check_agent(3, now=0.0)[0])
        self.assertFalse(r.check_agent(3, now=0.5)[0])

    def test_quota_message_is_thai_friendly(self):
        self.assertIn("โควต้า", QUOTA_EXHAUSTED_MSG)
        for leak in ("HTTP", "429", "key="):
            self.assertNotIn(leak, QUOTA_EXHAUSTED_MSG)


if __name__ == "__main__":
    unittest.main()
