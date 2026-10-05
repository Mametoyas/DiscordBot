"""Usage counters: per-model + per-key aggregation, no network."""

import unittest

from src.core.llm import GeminiRotator


class TestUsage(unittest.TestCase):
    def setUp(self):
        self.r = GeminiRotator(["k1", "k2"], "gemini-3.5-flash-lite")

    def test_record_ok(self):
        self.r._record("gemini-3.5-flash-lite", 0, True, 10, 20)
        u = self.r.usage["gemini-3.5-flash-lite"]
        self.assertEqual((u["requests"], u["ok"], u["errors"]), (1, 1, 0))
        self.assertEqual((u["in_tokens"], u["out_tokens"]), (10, 20))
        self.assertEqual(self.r.key_stats[0]["ok"], 1)

    def test_record_error(self):
        self.r._record("gemini-3.5-flash-lite", 1, False, err="HTTP 429: quota")
        u = self.r.usage["gemini-3.5-flash-lite"]
        self.assertEqual((u["requests"], u["errors"]), (1, 1))
        self.assertIn("429", u["last_error"])
        self.assertEqual(self.r.key_stats[1]["errors"], 1)

    def test_add_keys_grows_stats(self):
        self.r.add_keys(["k3"])
        self.assertEqual(len(self.r.key_stats), 3)

    def test_status_shape(self):
        self.r._record("gemini-3.5-flash-lite", 0, True, 1, 2)
        s = self.r.status()
        self.assertEqual(s["provider"], "gemini")
        self.assertIn("gemini-3.5-flash-lite", s["usage"])
        self.assertEqual(len(s["key_usage"]), 2)
        self.r.set_model("openai/gpt-oss-120b")
        self.assertEqual(self.r.status()["provider"], "groq")


if __name__ == "__main__":
    unittest.main()
