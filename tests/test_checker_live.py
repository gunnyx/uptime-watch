import time
import unittest

from tests.helpers import FakeHTTPTarget, make_db_path, wait_for
from uptimewatch.checker import Checker
from uptimewatch.db import Database
from uptimewatch.targets import Target

HTTP = {"name": "ui1", "type": "http", "url": None, "expected_status": 200, "interval": 5}


class LiveTests(unittest.TestCase):
    def setUp(self):
        path, cleanup = make_db_path()
        self.addCleanup(cleanup)
        self.db = Database(path)
        self.a = FakeHTTPTarget()
        self.b = FakeHTTPTarget()
        self.addCleanup(self.a.stop)
        self.addCleanup(self.b.stop)

    def start(self, config_targets=()):
        c = Checker(self.db, list(config_targets), timeout=2, retention_days=30, tick=0.05, ui_poll=0.1)
        self.addCleanup(c.stop)
        c.start()
        return c

    def add(self, **kw):
        f = dict(HTTP, url=self.a.url)
        f.update(kw)
        return self.db.add_ui_target(f, int(time.time()))

    def count(self, name):
        return len(self.db.results_since(name, 0))

    def test_added_target_checked_quickly(self):
        self.start()
        t0 = time.monotonic()
        self.add()
        self.assertTrue(wait_for(lambda: self.count("ui1") >= 1, 5))
        self.assertLess(time.monotonic() - t0, 5)

    def test_edit_changes_url(self):
        self.start()
        i = self.add()
        self.assertTrue(wait_for(lambda: self.a.hits >= 1, 5))
        self.assertEqual(self.b.hits, 0)
        self.db.update_ui_target(i, dict(HTTP, url=self.b.url), int(time.time()) + 1)
        self.assertTrue(wait_for(lambda: self.b.hits >= 1, 5))

    def test_pause_and_resume(self):
        self.start()
        i = self.add()
        self.assertTrue(wait_for(lambda: self.count("ui1") >= 1, 5))
        self.db.set_paused(i, True, int(time.time()) + 1)
        time.sleep(0.5)
        n = self.count("ui1")
        time.sleep(0.5)
        self.assertEqual(self.count("ui1"), n)
        self.db.set_paused(i, False, int(time.time()) + 2)
        self.assertTrue(wait_for(lambda: self.count("ui1") > n, 5))

    def test_delete_stops_checks(self):
        c = self.start()
        i = self.add()
        self.assertTrue(wait_for(lambda: self.count("ui1") >= 1, 5))
        self.db.delete_ui_target(i)
        self.assertTrue(wait_for(lambda: "ui1" not in c._due, 3))
        time.sleep(0.3)
        n = self.count("ui1")
        time.sleep(0.5)
        self.assertEqual(self.count("ui1"), n)

    def test_config_targets_unaffected(self):
        cfg = Target(name="cfg", type="http", url=self.a.url, expected_status=200, interval=0.2)
        self.start([cfg])
        i = self.add()
        self.db.set_paused(i, True, int(time.time()) + 1)
        self.db.delete_ui_target(i)
        self.assertTrue(wait_for(lambda: self.count("cfg") >= 4, 5))

    def test_name_collision_keeps_config(self):
        cfg = Target(name="Same", type="http", url=self.a.url, expected_status=200, interval=0.2)
        self.start([cfg])
        self.add(name="same", url=self.b.url)
        self.assertTrue(wait_for(lambda: self.count("Same") >= 3, 5))
        self.assertEqual(self.b.hits, 0)


if __name__ == "__main__":
    unittest.main()
