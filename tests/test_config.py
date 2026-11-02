import json
import os
import unittest

from tests.helpers import TempDir
from uptimewatch.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.t = TempDir()
        self.addCleanup(self.t.cleanup)
        self._env = os.environ.pop("UPTIME_ADMIN_TOKEN", None)
        self.addCleanup(self._restore)

    def _restore(self):
        os.environ.pop("UPTIME_ADMIN_TOKEN", None)
        if self._env is not None:
            os.environ["UPTIME_ADMIN_TOKEN"] = self._env

    def load(self, data):
        p = self.t.file("c.json")
        with open(p, "w") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        return load_config(p)

    def err(self, data):
        with self.assertRaises(ConfigError) as cm:
            self.load(data)
        return str(cm.exception)

    def test_defaults(self):
        c = self.load({})
        self.assertEqual(c.database, "uptime.db")
        self.assertEqual(c.default_timeout, 10)
        self.assertEqual(c.retention_days, 30)
        self.assertEqual(c.discord_webhook_url, "")
        self.assertEqual((c.host, c.port), ("127.0.0.1", 8080))
        self.assertEqual(c.targets, [])
        self.assertEqual(c.admin_token, "")

    def test_targets_parsed(self):
        c = self.load({"targets": [
            {"name": "a", "type": "http", "url": "http://x"},
            {"name": "b", "type": "tcp", "host": "h", "port": 5, "interval": 30}]})
        a, b = c.targets
        self.assertEqual((a.expected_status, a.interval, a.source), (200, 60, "config"))
        self.assertEqual((b.host, b.port, b.interval), ("h", 5, 30))

    def test_unknown_keys(self):
        self.assertIn("bogus", self.err({"bogus": 1}))
        self.assertIn("server.bogus", self.err({"server": {"bogus": 1}}))
        m = self.err({"targets": [{"name": "a", "type": "http", "url": "http://x", "bogus": 1}]})
        self.assertIn("targets[0].bogus", m)

    def test_wrong_types(self):
        self.assertIn("default_timeout", self.err({"default_timeout": "x"}))
        self.assertIn("default_timeout", self.err({"default_timeout": 0}))
        self.assertIn("retention_days", self.err({"retention_days": 0}))
        self.assertIn("retention_days", self.err({"retention_days": 1.5}))
        self.assertIn("server.port", self.err({"server": {"port": 70000}}))
        self.assertIn("server.port", self.err({"server": {"port": True}}))
        self.assertIn("database", self.err({"database": 3}))
        self.assertIn("targets", self.err({"targets": {}}))
        self.assertIn("invalid JSON", self.err("{nope"))
        self.assertIn("object", self.err("[]"))

    def test_field_rules(self):
        base = {"name": "a", "type": "http", "url": "http://x"}
        self.assertIn("url", self.err({"targets": [{"name": "a", "type": "http"}]}))
        self.assertIn("host", self.err({"targets": [{"name": "a", "type": "tcp", "port": 1}]}))
        self.assertIn("host", self.err({"targets": [dict(base, host="h")]}))
        self.assertIn("url", self.err({"targets": [{"name": "a", "type": "tcp", "host": "h", "port": 1, "url": "http://x"}]}))
        self.assertIn("interval", self.err({"targets": [dict(base, interval=4)]}))
        self.assertIn("url", self.err({"targets": [dict(base, url="ftp://x")]}))

    def test_duplicate_and_name_length(self):
        t = {"name": "a", "type": "http", "url": "http://x"}
        self.assertIn("duplicate", self.err({"targets": [t, dict(t, name="A")]}))
        self.assertIn("name", self.err({"targets": [dict(t, name="")]}))
        self.assertIn("name", self.err({"targets": [dict(t, name="x" * 65)]}))
        self.load({"targets": [dict(t, name="x" * 64)]})

    def test_env_token_overrides(self):
        self.assertEqual(self.load({"admin_token": "cfg"}).admin_token, "cfg")
        os.environ["UPTIME_ADMIN_TOKEN"] = "env"
        self.assertEqual(self.load({"admin_token": "cfg"}).admin_token, "env")
        os.environ["UPTIME_ADMIN_TOKEN"] = ""
        self.assertEqual(self.load({"admin_token": "cfg"}).admin_token, "cfg")

    def test_errors_do_not_echo_secrets(self):
        m = self.err({"admin_token": 5, "discord_webhook_url": "https://discord/SECRETHOOK", "bogus": "x"})
        self.assertNotIn("SECRETHOOK", m)
        m = self.err({"admin_token": "TOKENVALUE", "discord_webhook_url": 7})
        self.assertNotIn("TOKENVALUE", m)
        m = self.err({"discord_webhook_url": 7, "admin_token": 9})
        self.assertNotIn("9", m.replace("admin_token", ""))

    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_config(self.t.file("nope.json"))


if __name__ == "__main__":
    unittest.main()
