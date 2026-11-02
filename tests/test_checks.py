import unittest

from tests.helpers import FakeHTTPTarget, FakeTCPTarget, closed_port
from uptimewatch.checks import check_http, check_tcp


class HttpChecks(unittest.TestCase):
    def setUp(self):
        self.t = FakeHTTPTarget()
        self.addCleanup(self.t.stop)

    def test_ok(self):
        r = check_http(self.t.url, 200, 2)
        self.assertTrue(r.ok)
        self.assertEqual(r.error, "")
        self.assertGreaterEqual(r.latency_ms, 0)

    def test_other_status_fails(self):
        for code in (404, 500):
            self.t.status = code
            r = check_http(self.t.url, 200, 2)
            self.assertFalse(r.ok)
            self.assertIn(str(code), r.error)

    def test_expected_status_matches_non_200(self):
        self.t.status = 404
        self.assertTrue(check_http(self.t.url, 404, 2).ok)

    def test_redirect_not_followed(self):
        self.t.status = 301
        r = check_http(self.t.url, 200, 2)
        self.assertFalse(r.ok)
        self.assertIn("301", r.error)
        self.assertTrue(check_http(self.t.url, 301, 2).ok)

    def test_timeout(self):
        self.t.delay = 1.0
        r = check_http(self.t.url, 200, 0.2)
        self.assertFalse(r.ok)
        self.assertTrue(r.error)

    def test_refused(self):
        r = check_http("http://127.0.0.1:%d/" % closed_port(), 200, 2)
        self.assertFalse(r.ok)
        self.assertLessEqual(len(r.error), 200)

    def test_error_truncated(self):
        r = check_http("http://" + "a" * 500 + ".invalid/", 200, 2)
        self.assertFalse(r.ok)
        self.assertLessEqual(len(r.error), 200)


class TcpChecks(unittest.TestCase):
    def test_ok(self):
        t = FakeTCPTarget()
        self.addCleanup(t.stop)
        r = check_tcp("127.0.0.1", t.port, 2)
        self.assertTrue(r.ok)
        self.assertGreaterEqual(r.latency_ms, 0)

    def test_fail(self):
        r = check_tcp("127.0.0.1", closed_port(), 2)
        self.assertFalse(r.ok)
        self.assertTrue(r.error)

    def test_timeout(self):
        # TEST-NET address: connection attempt cannot succeed
        r = check_tcp("10.255.255.1", 81, 0.2)
        self.assertFalse(r.ok)
        self.assertTrue(r.error)


if __name__ == "__main__":
    unittest.main()
