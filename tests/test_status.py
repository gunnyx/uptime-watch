import time
import unittest
from datetime import datetime, timezone

from tests.helpers import make_db_path
from uptimewatch.db import Database
from uptimewatch.status import build_status
from uptimewatch.targets import Target

NOW = 1_800_000_000


def T(name, **kw):
    return Target(name=name, type="http", url="http://x", expected_status=200, interval=30, **kw)


class StatusTests(unittest.TestCase):
    def setUp(self):
        path, cleanup = make_db_path()
        self.addCleanup(cleanup)
        self.db = Database(path)

    def one(self, targets):
        return build_status(self.db, targets, NOW)

    def test_unknown_when_no_results(self):
        s = self.one([T("a")])
        t = s["targets"][0]
        self.assertEqual((t["state"], t["uptime_24h"], t["last_check"], t["latency_ms"]), ("unknown", None, None, None))
        self.assertEqual(s["overall"], "unknown")

    def test_up_down_and_fields(self):
        self.db.insert_result(NOW - 10, "a", True, 41.2, "")
        self.db.insert_result(NOW - 5, "b", False, None, "boom")
        s = self.one([T("a"), T("b")])
        a, b = s["targets"]
        self.assertEqual(a["state"], "up")
        self.assertEqual(a["latency_ms"], 41.2)
        self.assertEqual(a["last_check"], datetime.fromtimestamp(NOW - 10, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.assertEqual(b["state"], "down")
        self.assertEqual(b["error"], "boom")
        self.assertEqual(s["overall"], "down")
        self.assertEqual(a["source"], "config")

    def test_uptime_rounding_and_window(self):
        self.db.insert_result(NOW - 90000, "a", False, None, "old")  # excluded
        self.db.insert_result(NOW - 300, "a", True, 1, "")
        self.db.insert_result(NOW - 200, "a", True, 1, "")
        self.db.insert_result(NOW - 100, "a", False, None, "x")
        t = self.one([T("a")])["targets"][0]
        self.assertEqual(t["uptime_24h"], 66.7)
        self.assertEqual(t["state"], "down")

    def test_old_results_only_gives_null_uptime(self):
        self.db.insert_result(NOW - 90000, "a", True, 1, "")
        t = self.one([T("a")])["targets"][0]
        self.assertIsNone(t["uptime_24h"])
        self.assertEqual(t["state"], "up")

    def test_paused_and_overall(self):
        self.db.insert_result(NOW - 5, "a", True, 1, "")
        self.db.insert_result(NOW - 5, "p", False, None, "x")
        s = self.one([T("a"), T("p", paused=True)])
        self.assertEqual(s["targets"][1]["state"], "paused")
        self.assertEqual(s["overall"], "up")
        self.assertEqual(self.one([T("p", paused=True)])["overall"], "none")
        self.assertEqual(self.one([])["overall"], "none")

    def test_overall_unknown_when_some_unknown(self):
        self.db.insert_result(NOW - 5, "a", True, 1, "")
        self.assertEqual(self.one([T("a"), T("b")])["overall"], "unknown")

    def test_down_beats_unknown(self):
        self.db.insert_result(NOW - 5, "a", False, None, "x")
        self.assertEqual(self.one([T("a"), T("b")])["overall"], "down")

    def test_generated_at_and_management_flag(self):
        s = build_status(self.db, [], NOW, management_enabled=True)
        self.assertTrue(s["management_enabled"])
        self.assertTrue(s["generated_at"].endswith("Z"))
        self.assertFalse(self.one([])["management_enabled"])


if __name__ == "__main__":
    unittest.main()
