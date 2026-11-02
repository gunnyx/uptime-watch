import sqlite3
import unittest

from tests.helpers import make_db_path
from uptimewatch.db import Database, DatabaseError


class DbTests(unittest.TestCase):
    def setUp(self):
        self.path, cleanup = make_db_path()
        self.addCleanup(cleanup)
        self.db = Database(self.path)

    def test_schema_idempotent_and_wal(self):
        Database(self.path)
        c = sqlite3.connect(self.path)
        names = {r[0] for r in c.execute("select name from sqlite_master")}
        for n in ("results", "ui_targets", "target_state", "idx_results_target_ts", "idx_results_ts"):
            self.assertIn(n, names)
        self.assertEqual(c.execute("pragma journal_mode").fetchone()[0], "wal")

    def test_results(self):
        self.db.insert_result(100, "a", True, 12.5, "")
        self.db.insert_result(200, "a", False, None, "boom")
        rows = self.db.results_since("a", 0)
        self.assertEqual([(r["ts"], r["ok"]) for r in rows], [(100, 1), (200, 0)])
        self.assertEqual(self.db.latest_result("a")["error"], "boom")
        self.assertIsNone(self.db.latest_result("zzz"))
        self.assertEqual(len(self.db.results_since("a", 150)), 1)

    def test_ui_targets_crud(self):
        fields = {"name": "Web", "type": "http", "url": "http://x", "expected_status": 200, "interval": 30}
        i = self.db.add_ui_target(fields, 1000)
        row = self.db.get_ui_target(i)
        self.assertEqual(row["name"], "Web")
        self.assertEqual(row["paused"], 0)
        with self.assertRaises(DatabaseError):
            self.db.add_ui_target(dict(fields, name="web"), 1000)
        self.db.update_ui_target(i, dict(fields, name="Web2", interval=60), 2000)
        row = self.db.get_ui_target(i)
        self.assertEqual((row["name"], row["interval"], row["updated_at"]), ("Web2", 60, 2000))
        self.db.set_paused(i, True, 3000)
        self.assertEqual(self.db.get_ui_target(i)["paused"], 1)
        self.assertEqual(len(self.db.list_ui_targets()), 1)
        self.assertEqual(self.db.count_ui_targets(), 1)
        self.db.upsert_state("Web2", "up", 1)
        self.assertTrue(self.db.delete_ui_target(i))
        self.assertFalse(self.db.delete_ui_target(i))
        self.assertIsNone(self.db.get_ui_target(i))
        self.assertIsNone(self.db.get_state("Web2"))

    def test_target_state_upsert(self):
        self.assertIsNone(self.db.get_state("a"))
        self.db.upsert_state("a", "up", 10)
        self.db.upsert_state("a", "down", 20)
        s = self.db.get_state("a")
        self.assertEqual((s["state"], s["since"]), ("down", 20))

    def test_unwritable(self):
        with self.assertRaises(DatabaseError):
            Database("/nonexistent-dir/x/y.db")


if __name__ == "__main__":
    unittest.main()
