import io
import logging
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from tests.helpers import (FakeHTTPTarget, FakeWebhook, base_config, closed_port, make_db_path, request,
                           start_app, wait_for)
from uptimewatch.config import parse_config

TOKEN = "SENTINEL-TOKEN-8f3a"


class SecretLeakTests(unittest.TestCase):
    def test_full_session_leaks_nothing(self):
        os.environ.pop("UPTIME_ADMIN_TOKEN", None)
        log_stream, err, out = io.StringIO(), io.StringIO(), io.StringIO()
        handler = logging.StreamHandler(log_stream)
        root = logging.getLogger()
        old_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        self.addCleanup(root.removeHandler, handler)
        self.addCleanup(root.setLevel, old_level)

        hook = FakeWebhook()
        self.addCleanup(hook.stop)
        fake = FakeHTTPTarget()
        self.addCleanup(fake.stop)
        path, cleanup = make_db_path()
        self.addCleanup(cleanup)
        webhook_url = hook.url  # contains /webhook/SECRET
        with redirect_stderr(err), redirect_stdout(out):
            cfg = parse_config(base_config(path, [
                {"name": "svc", "type": "http", "url": fake.url, "interval": 5},
                {"name": "dead", "type": "tcp", "host": "127.0.0.1", "port": closed_port(), "interval": 5},
            ], admin_token=TOKEN, discord_webhook_url=webhook_url))
            base, stop, app = start_app(cfg)
            app.checker.timeout = 1
            try:
                wait_for(lambda: app.db.latest_result("dead") is not None, 5)
                request("POST", base + "/api/targets", token="wrong", body={})
                request("POST", base + "/api/targets", token=TOKEN, body={
                    "name": "u", "type": "tcp", "host": "127.0.0.1", "port": closed_port(), "interval": 5})
                request("POST", base + "/api/targets", token=TOKEN, body={"bad": 1})
                request("GET", base + "/status")
                fake.status = 500
                # force a transition through the alerter directly to exercise delivery quickly
                app.checker.alerter.observe("svc", True, "")
                app.checker.alerter.observe("svc", False, "boom")
                wait_for(lambda: len(hook.bodies) >= 1, 5)
            finally:
                stop()
        blob = log_stream.getvalue() + err.getvalue() + out.getvalue()
        self.assertTrue(hook.bodies, "alert should have been delivered")
        self.assertNotIn(TOKEN, blob)
        self.assertNotIn("/webhook/SECRET", blob)
        self.assertNotIn("SECRET", blob)


if __name__ == "__main__":
    unittest.main()
