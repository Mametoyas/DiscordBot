"""ENHANCE.md Phase 7: SQLite fallback persistence (stdlib only)."""

import asyncio
import os
import tempfile
import unittest


class TestSqliteFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = os.path.join(self.tmp.name, "chat.db")
        # re-read env into module + fresh store with Supabase disabled
        import src.utils.chat_store as cs
        cs.SQLITE_PATH = os.environ["SQLITE_PATH"]
        os.environ.pop("SUPABASE_URL", None)
        os.environ.pop("SUPABASE_KEY", None)
        self.cs = cs
        self.store = cs.ChatStore()
        self.assertFalse(self.store.enabled)

    def tearDown(self):
        self.tmp.cleanup()

    def test_chat_roundtrip(self):
        async def go():
            await self.store.add("ch1", "u1", "user", "สวัสดี", "g1")
            await self.store.add("ch1", "u1", "model", "ดีจ้า", "g1")
            return await self.store.get("ch1")
        msgs = asyncio.run(go())
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["text"], "สวัสดี")

    def test_alias_roundtrip(self):
        async def go():
            await self.store.set_alias("g1", "ตี้พับจี-นำ", "u42", "u1")
            hit = await self.store.get_alias("g1", "ตี้พับจี-นำ")
            ok = await self.store.remove_alias("g1", "ตี้พับจี-นำ")
            return hit, ok
        hit, ok = asyncio.run(go())
        self.assertEqual(hit, "u42")
        self.assertTrue(ok)

    def test_fact_roundtrip_and_forget(self):
        async def go():
            await self.store.remember_fact("g1", "ตี้พับจี", "A, B", "general", "u1")
            rows = await self.store.recall_matching("g1", "ตี้พับจี")
            ok = await self.store.forget_fact("g1", "ตี้พับจี")
            return rows, ok
        rows, ok = asyncio.run(go())
        self.assertTrue(any(r["key"] == "ตี้พับจี" for r in rows))
        self.assertTrue(ok)

    def test_forget_me_clears_user(self):
        async def go():
            await self.store.add("ch9", "uX", "user", "secret hello", "g9")
            await self.store.set_alias("g9", "ฉายาX", "uX", "uX")
            counts = await self.store.delete_user_data("g9", "uX")
            info = await self.store.user_data_summary("g9", "uX")
            return counts, info
        counts, info = asyncio.run(go())
        self.assertGreaterEqual(counts["chat"] + counts["aliases"], 1)
        self.assertEqual(info["aliases"], [])


if __name__ == "__main__":
    unittest.main()
