import unittest

from uptimewatch.targets import validate_target_input


def http(**kw):
    d = {"name": "n", "type": "http", "url": "http://x", "interval": 30}
    d.update(kw)
    return d


def tcp(**kw):
    d = {"name": "n", "type": "tcp", "host": "h", "port": 80, "interval": 30}
    d.update(kw)
    return d


class ValidationTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_target_input(http()), {})
        self.assertEqual(validate_target_input(tcp()), {})

    def test_name(self):
        self.assertIn("name", validate_target_input(http(name="   ")))
        self.assertIn("name", validate_target_input(http(name="x" * 65)))
        self.assertIn("name", validate_target_input(http(name=5)))
        self.assertEqual(validate_target_input(http(name="  " + "x" * 64 + " ")), {})
        d = http()
        del d["name"]
        self.assertIn("name", validate_target_input(d))

    def test_type(self):
        self.assertIn("type", validate_target_input(http(type="ping")))

    def test_url(self):
        self.assertIn("url", validate_target_input(http(url="ftp://x")))
        self.assertIn("url", validate_target_input(http(url="")))
        self.assertEqual(validate_target_input(http(url="https://x")), {})

    def test_port(self):
        for bad in (0, 65536, True, "80", 1.5):
            self.assertIn("port", validate_target_input(tcp(port=bad)), bad)
        self.assertEqual(validate_target_input(tcp(port=65535)), {})

    def test_interval(self):
        for bad in (4, True, "30", 5.5, None):
            self.assertIn("interval", validate_target_input(http(interval=bad)), bad)
        self.assertEqual(validate_target_input(http(interval=5)), {})

    def test_expected_status(self):
        for bad in (99, 600, True, "200"):
            self.assertIn("expected_status", validate_target_input(http(expected_status=bad)), bad)
        self.assertEqual(validate_target_input(http(expected_status=100)), {})

    def test_tcp_requires_host_port(self):
        d = tcp()
        del d["host"]
        self.assertIn("host", validate_target_input(d))
        d = tcp()
        del d["port"]
        self.assertIn("port", validate_target_input(d))

    def test_cross_type_fields_rejected(self):
        self.assertIn("host", validate_target_input(http(host="h")))
        self.assertIn("port", validate_target_input(http(port=1)))
        self.assertIn("url", validate_target_input(tcp(url="http://x")))
        self.assertIn("expected_status", validate_target_input(tcp(expected_status=200)))

    def test_unknown_fields(self):
        self.assertIn("bogus", validate_target_input(http(bogus=1)))

    def test_paused_allowed_only_when_enabled(self):
        self.assertEqual(validate_target_input(http(paused=True), allow_paused=True), {})
        self.assertIn("paused", validate_target_input(http(paused=1), allow_paused=True))
        self.assertIn("paused", validate_target_input(http(paused=True)))


if __name__ == "__main__":
    unittest.main()
