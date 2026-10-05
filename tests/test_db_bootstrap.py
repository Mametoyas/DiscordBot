"""SQL splitter must keep DO $$ blocks intact and split plain DDL."""

import unittest

from src.utils.db_bootstrap import split_statements, _schema_sql


class TestSplitStatements(unittest.TestCase):
    def test_simple_split(self):
        self.assertEqual(len(split_statements("create table a (x int); create table b (y int);")), 2)

    def test_do_block_intact(self):
        sql = "create table a (x int); do $$ begin if true then raise notice 'hi;'; end if; end $$;"
        stmts = split_statements(sql)
        self.assertEqual(len(stmts), 2)
        self.assertIn("do $$", stmts[1])

    def test_full_schema_splits(self):
        stmts = split_statements(_schema_sql())
        tables = [s for s in stmts if "create table" in s.lower()]
        self.assertGreaterEqual(len(tables), 3)  # chat_history, member_aliases, memories
        joined = "\n".join(stmts).lower()
        for t in ("chat_history", "member_aliases", "memories"):
            self.assertIn(t, joined)


if __name__ == "__main__":
    unittest.main()
