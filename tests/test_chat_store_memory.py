"""Local-mode memory: aliases + facts with miss-to-recent fallbacks (no network)."""

import os
import unittest

os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)

from src.utils import chat_store
from src.utils.chat_store import ChatStore


class TestLocalMemory(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        chat_store._memory_local.clear()
        chat_store._alias_local.clear()
        self.store = ChatStore()
        self.assertFalse(self.store.enabled)

    async def test_alias_roundtrip(self):
        await self.store.set_alias("g1", "หม่อม", "111", "999")
        self.assertEqual(await self.store.get_alias("g1", "หม่อม"), "111")
        self.assertEqual(await self.store.aliases_for_member("g1", "111"), ["หม่อม"])
        self.assertTrue(await self.store.remove_alias("g1", "หม่อม"))
        self.assertIsNone(await self.store.get_alias("g1", "หม่อม"))

    async def test_recall_hit(self):
        await self.store.remember_fact("g1", "ตี้พับจี", "เต้ย โขง", "general", "999")
        rows = await self.store.recall_matching("g1", "ตี้พับจีมีใคร")
        self.assertTrue(any(r["key"] == "ตี้พับจี" for r in rows))

    async def test_recall_miss_falls_back_to_recent(self):
        await self.store.remember_fact("g1", "ตี้พับจี", "เต้ย โขง", "general", "999")
        rows = await self.store.recall_matching("g1", "PUBG คำที่ไม่มีวันตรง xyz")
        self.assertTrue(any(r["key"] == "ตี้พับจี" for r in rows))

    async def test_forget(self):
        await self.store.remember_fact("g1", "k", "v", "general", "999")
        self.assertTrue(await self.store.forget_fact("g1", "k"))
        self.assertFalse(await self.store.forget_fact("g1", "k"))


if __name__ == "__main__":
    unittest.main()
