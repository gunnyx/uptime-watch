import io
import logging
import time
import unittest

from tests.helpers import FakeHTTPTarget, FakeWebhook, make_db_path, wait_for
from uptimewatch.alerts import Alerter
from uptimewatch.checker import Checker
from uptimewatch.db import Database
from uptimewatch.targets import Target


class AlertTests(unittest.TestCase):
    def setUp(self):
        path, cleanup = make_db_path()
        self.addCleanup(cleanup)
        self.db = Database(path)
        self.hook = FakeWebhook()
        self.addCleanup(self.hook.stop)

    def alerter(self, url=None):
        a = Alerter(self.db, self.hook.url if url is None else url, timeout=1)
        self.addCleanup(a.close)
        return a

    def test_first_observation_no_alert(self):
        a = self.alerter()
        a.observe("t", False, "boom")
        a.close()
        self.assertEqual(self.hook.bodies, [])
        self.assertEqual(self.db.get_state("t")["state"], "down")

    def test_down_then_repeats_then_up(self):
        a = self.alerter()
        a.observe("t", True, "")
        a.observe("t", False, "refused")
        for _ in range(5):
            a.observe("t", False, "refused")
        self.assertTrue(wait_for(lambda: len(self.hook.bodies) == 1, 3))
        a.observe("t", True, "")
        self.assertTrue(wait_for(lambda: len(self.hook.bodies) == 2, 3))
        a.observe("t", True, "")
        time.sleep(0.2)
        self.assertEqual(len(self.hook.bodies), 2)
        down, up = (b["content"] for b in self.hook.bodies)
        self.assertIn("t", down)
        self.assertIn("DOWN", down)
        self.assertIn("refused", down)
        self.assertIn("UP", up)

    def test_state_persisted_across_restart(self):
        a = self.alerter()
        a.observe("t", False, "x")  # baseline: down
        a.close()
        b = self.alerter()
        b.observe("t", False, "x")
        time.sleep(0.2)
        self.assertEqual(self.hook.bodies, [])
        b.observe("t", True, "")
        self.assertTrue(wait_for(lambda: len(self.hook.bodies) == 1, 3))

    def test_webhook_failure_does_not_raise(self):
        a = self.alerter(url="http://127.0.0.1:1/dead")
        a.observe("t", True, "")
        a.observe("t", False, "x")
        a.close()
        self.hook.status = 500
        slow = FakeWebhook(delay=2.0)
        self.addCleanup(slow.stop)
        b = Alerter(self.db, slow.url, timeout=0.3)
        b.observe("u", True, "")
        t0 = time.monotonic()
        b.observe("u", False, "x")
        self.assertLess(time.monotonic() - t0, 0.2)  # non-blocking
        b.close()

    def test_no_webhook_no_calls(self):
        a = Alerter(self.db, "", timeout=1)
        a.observe("t", True, "")
        a.observe("t", False, "x")
        a.close()
        self.assertEqual(self.hook.bodies, [])
        self.assertEqual(self.db.get_state("t")["state"], "down")

    def test_webhook_url_not_logged(self):
        stream = io.StringIO()
        h = logging.StreamHandler(stream)
        root = logging.getLogger()
        root.addHandler(h)
        root.setLevel(logging.DEBUG)
        self.addCleanup(root.removeHandler, h)
        a = Alerter(self.db, "http://127.0.0.1:1/hooks/SECRETHOOK", timeout=0.5)
        a.observe("t", True, "")
        a.observe("t", False, "x")
        a.close()
        self.assertNotIn("SECRETHOOK", stream.getvalue())

    def test_checker_integration(self):
        fake = FakeHTTPTarget()
        self.addCleanup(fake.stop)
        t = Target(name="svc", type="http", url=fake.url, expected_status=200, interval=0.15)
        c = Checker(self.db, [t], timeout=1, retention_days=30, tick=0.03, alerter=self.alerter())
        self.addCleanup(c.stop)
        c.start()
        self.assertTrue(wait_for(lambda: len(self.db.results_since("svc", 0)) >= 2, 3))
        fake.status = 500
        self.assertTrue(wait_for(lambda: len(self.hook.bodies) == 1, 3))
        time.sleep(0.8)  # several more failures
        self.assertEqual(len(self.hook.bodies), 1)
        fake.status = 200
        self.assertTrue(wait_for(lambda: len(self.hook.bodies) == 2, 3))


if __name__ == "__main__":
    unittest.main()
