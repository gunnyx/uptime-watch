import time
import unittest

from tests.helpers import FakeHTTPTarget, make_db_path, wait_for
from uptimewatch.checker import Checker
from uptimewatch.db import Database
from uptimewatch.targets import Target


def T(name, url, interval=0.2):
    return Target(name=name, type="http", url=url, expected_status=200, interval=interval)


class CheckerTests(unittest.TestCase):
    def setUp(self):
        path, cleanup = make_db_path()
        self.addCleanup(cleanup)
        self.db = Database(path)
        self.fake = FakeHTTPTarget()
        self.addCleanup(self.fake.stop)

    def make(self, targets, **kw):
        c = Checker(self.db, targets, timeout=2, retention_days=30, tick=0.02, **kw)
        self.addCleanup(c.stop)
        return c

    def count(self, name):
        return len(self.db.results_since(name, 0))

    def test_checked_repeatedly_and_recorded(self):
        c = self.make([T("a", self.fake.url)])
        c.start()
        self.assertTrue(wait_for(lambda: self.count("a") >= 3, 5))
        r = self.db.latest_result("a")
        self.assertEqual(r["ok"], 1)
        self.assertIsNotNone(r["latency_ms"])

    def test_failure_recorded(self):
        self.fake.status = 500
        c = self.make([T("a", self.fake.url)])
        c.start()
        self.assertTrue(wait_for(lambda: self.count("a") >= 1, 5))
        self.assertEqual(self.db.latest_result("a")["ok"], 0)

    def test_slow_target_does_not_delay_fast(self):
        slow = FakeHTTPTarget(delay=1.0)
        self.addCleanup(slow.stop)
        c = self.make([T("slow", slow.url, 0.2), T("fast", self.fake.url, 0.2)])
        c.start()
        self.assertTrue(wait_for(lambda: self.count("fast") >= 4, 3))
        self.assertLessEqual(self.count("slow"), 2)

    def test_never_concurrent_with_itself(self):
        slow = FakeHTTPTarget(delay=0.6)
        self.addCleanup(slow.stop)
        peak = {"cur": 0, "max": 0}
        orig = slow.server.RequestHandlerClass.do_GET

        def wrapped(h):
            peak["cur"] += 1
            peak["max"] = max(peak["max"], peak["cur"])
            try:
                orig(h)
            finally:
                peak["cur"] -= 1

        slow.server.RequestHandlerClass.do_GET = wrapped
        c = self.make([T("s", slow.url, 0.1)])
        c.start()
        time.sleep(1.5)
        c.stop()
        self.assertEqual(peak["max"], 1)

    def test_prune_at_startup(self):
        self.db.insert_result(int(time.time()) - 40 * 86400, "old", True, 1, "")
        c = self.make([])
        c.start()
        self.assertTrue(wait_for(lambda: self.count("old") == 0, 3))

    def test_clean_stop(self):
        c = self.make([T("a", self.fake.url)])
        c.start()
        c.stop()
        self.assertFalse(c.thread.is_alive())
        n = self.count("a")
        time.sleep(0.5)
        self.assertEqual(self.count("a"), n)


if __name__ == "__main__":
    unittest.main()
