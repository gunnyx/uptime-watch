import io
import logging
import os
import unittest

from tests.helpers import base_config, make_db_path, request, start_app
from uptimewatch.config import parse_config

TOKEN = "s3cret-token-xyz"
GOOD = {"name": "n1", "type": "tcp", "host": "127.0.0.1", "port": 80, "interval": 30}


class AuthBase(unittest.TestCase):
    token = TOKEN

    def setUp(self):
        os.environ.pop("UPTIME_ADMIN_TOKEN", None)
        path, cleanup = make_db_path()
        self.addCleanup(cleanup)
        extra = {"admin_token": self.token} if self.token else {}
        cfg = parse_config(base_config(path, **extra))
        self.base, stop, self.app = start_app(cfg)
        self.addCleanup(stop)
        self.url = self.base + "/api/targets"


class AuthTests(AuthBase):
    def calls(self):
        return [("POST", self.url, GOOD), ("PUT", self.url + "/1", GOOD), ("DELETE", self.url + "/1", None)]

    def test_missing_wrong_scheme_401(self):
        for m, u, b in self.calls():
            self.assertEqual(request(m, u, body=b)[0], 401, m)
            self.assertEqual(request(m, u, body=b, token="wrong")[0], 401, m)
            self.assertEqual(request(m, u, body=b, headers={"Authorization": "Basic " + TOKEN})[0], 401, m)
            self.assertEqual(request(m, u, body=b, headers={"Authorization": TOKEN})[0], 401, m)
        self.assertEqual(self.app.db.count_ui_targets(), 0)

    def test_correct_token_succeeds(self):
        s, body, _ = request("POST", self.url, body=GOOD, token=TOKEN)
        self.assertEqual(s, 201)
        i = body["id"]
        self.assertEqual(request("PUT", "%s/%d" % (self.url, i), body=GOOD, token=TOKEN)[0], 200)
        self.assertEqual(request("DELETE", "%s/%d" % (self.url, i), token=TOKEN)[0], 204)

    def test_token_never_in_responses(self):
        for tok in (None, "wrong", TOKEN):
            _, body, h = request("POST", self.url, body=GOOD, token=tok)
            self.assertNotIn(TOKEN, str(body) + str(dict(h)))
        _, body, _ = request("GET", self.base + "/status")
        self.assertNotIn(TOKEN, str(body))
        self.assertTrue(body["management_enabled"])

    def test_token_not_in_logs(self):
        stream = io.StringIO()
        h = logging.StreamHandler(stream)
        logging.getLogger().addHandler(h)
        logging.getLogger().setLevel(logging.DEBUG)
        self.addCleanup(logging.getLogger().removeHandler, h)
        request("POST", self.url, body=GOOD, token=TOKEN)
        request("POST", self.url, body=GOOD, token="nope")
        self.assertNotIn(TOKEN, stream.getvalue())


class NoTokenTests(AuthBase):
    token = ""

    def test_403_even_with_header(self):
        for m, u, b in [("POST", self.url, GOOD), ("PUT", self.url + "/1", GOOD), ("DELETE", self.url + "/1", None)]:
            self.assertEqual(request(m, u, body=b)[0], 403)
            self.assertEqual(request(m, u, body=b, token="anything")[0], 403)
            self.assertEqual(request(m, u, body=b, token="")[0], 403)
        self.assertFalse(request("GET", self.base + "/status")[1]["management_enabled"])


class EnvTokenTests(unittest.TestCase):
    def test_env_token(self):
        path, cleanup = make_db_path()
        self.addCleanup(cleanup)
        os.environ["UPTIME_ADMIN_TOKEN"] = "envtok"
        self.addCleanup(os.environ.pop, "UPTIME_ADMIN_TOKEN", None)
        cfg = parse_config(base_config(path, admin_token="cfgtok"))
        base, stop, _ = start_app(cfg)
        self.addCleanup(stop)
        self.assertEqual(request("POST", base + "/api/targets", body=GOOD, token="cfgtok")[0], 401)
        self.assertEqual(request("POST", base + "/api/targets", body=GOOD, token="envtok")[0], 201)


if __name__ == "__main__":
    unittest.main()
