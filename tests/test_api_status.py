import unittest

from tests.helpers import FakeHTTPTarget, base_config, make_db_path, request, start_app, wait_for
from uptimewatch.config import parse_config


class StatusApiTests(unittest.TestCase):
    def setUp(self):
        path, cleanup = make_db_path()
        self.addCleanup(cleanup)
        self.fake = FakeHTTPTarget()
        self.addCleanup(self.fake.stop)
        cfg = parse_config(base_config(path, [
            {"name": "up", "type": "http", "url": self.fake.url, "interval": 5},
        ], admin_token="TOPSECRET", discord_webhook_url="http://127.0.0.1:9/hook/WEBSECRET"))
        self.base, stop, self.app = start_app(cfg)
        self.addCleanup(stop)

    def test_health(self):
        s, body, h = request("GET", self.base + "/health")
        self.assertEqual((s, body), (200, {"status": "ok"}))
        self.assertIn("application/json", h["Content-Type"])

    def test_status_shape(self):
        wait_for(lambda: request("GET", self.base + "/status")[1]["targets"][0]["state"] == "up", 5)
        s, body, _ = request("GET", self.base + "/status")
        self.assertEqual(s, 200)
        for k in ("generated_at", "overall", "management_enabled", "targets"):
            self.assertIn(k, body)
        t = body["targets"][0]
        self.assertEqual((t["name"], t["source"], t["state"], t["type"]), ("up", "config", "up", "http"))
        for k in ("latency_ms", "last_check", "uptime_24h", "paused", "interval", "url"):
            self.assertIn(k, t)

    def test_404_and_405(self):
        self.assertEqual(request("GET", self.base + "/nope")[0], 404)
        self.assertEqual(request("POST", self.base + "/status", body={})[0], 405)
        self.assertEqual(request("PUT", self.base + "/health", body={})[0], 405)
        self.assertEqual(request("DELETE", self.base + "/")[0], 405)

    def test_no_secrets_in_responses(self):
        for path in ("/status", "/health", "/", "/nope"):
            s, body, h = request("GET", self.base + path)
            text = str(body) + str(dict(h))
            self.assertNotIn("TOPSECRET", text)
            self.assertNotIn("WEBSECRET", text)


if __name__ == "__main__":
    unittest.main()
