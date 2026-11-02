import re
import unittest

from tests.helpers import base_config, make_db_path, request, start_app
from uptimewatch.config import parse_config


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path, cleanup = make_db_path()
        cls.cleanup = staticmethod(cleanup)
        cfg = parse_config(base_config(path))
        base, cls.stop, _ = start_app(cfg)
        cls.status, cls.body, cls.headers = request("GET", base + "/")

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.cleanup()

    def test_served_as_html(self):
        self.assertEqual(self.status, 200)
        self.assertIn("text/html", self.headers["Content-Type"])

    def test_no_external_requests(self):
        b = self.body
        self.assertIsNone(re.search(r"https?://", b))
        self.assertNotIn("<link", b)
        self.assertNotIn('src="http', b)
        self.assertNotIn("@import", b)
        self.assertNotIn("url(http", b)
        self.assertNotIn("<script src", b)

    def test_responsive_and_refresh(self):
        self.assertIn('<meta name="viewport"', self.body)
        self.assertIn("setInterval(", self.body)
        self.assertIn("15000", self.body)
        self.assertIn("fetch('/status'", self.body)
        self.assertIn('<meta name="color-scheme" content="light dark">', self.body)
        self.assertIn('lang="en"', self.body)

    def test_safe_dom(self):
        self.assertIn("textContent", self.body)
        self.assertNotIn("innerHTML", self.body)

    def test_banner_and_table(self):
        self.assertIn('id="banner"', self.body)
        self.assertIn("<table", self.body)
        self.assertIn("<main", self.body)
        self.assertIn("<h1", self.body)
        self.assertIn('aria-live="polite"', self.body)
        self.assertIn('role="alert"', self.body)
        self.assertIn("Cannot reach monitor", self.body)
        self.assertIn("prefers-color-scheme: dark", self.body)
        self.assertIn(":focus-visible", self.body)

    def test_management_ui(self):
        b = self.body
        for ident in ('id="f-name"', 'id="f-type"', 'id="f-url"', 'id="f-host"', 'id="f-port"',
                      'id="f-interval"', 'id="f-status"'):
            self.assertIn(ident, b)
        self.assertIn("Add target", b)
        self.assertIn("confirm(", b)
        self.assertIn("sessionStorage", b)
        self.assertIn("management_enabled", b)
        self.assertIn("source === 'ui'", b)
        self.assertIn("Authorization", b)
        self.assertIn("Token rejected. Enter it again.", b)
        self.assertIn("Admin token", b)
        self.assertIn("PUT", b)
        self.assertIn("DELETE", b)
        self.assertIn("aria-describedby", b)


if __name__ == "__main__":
    unittest.main()
