import os
import unittest

from tests.helpers import base_config, make_db_path, request, start_app, wait_for
from uptimewatch.config import parse_config

TOKEN = "tok"
HTTP = {"name": "My site", "type": "http", "url": "http://127.0.0.1:9/", "expected_status": 200, "interval": 30}
TCP = {"name": "DB", "type": "tcp", "host": "127.0.0.1", "port": 5432, "interval": 30}


class CrudTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("UPTIME_ADMIN_TOKEN", None)
        path, cleanup = make_db_path()
        self.addCleanup(cleanup)
        cfg = parse_config(base_config(path, [
            {"name": "cfgone", "type": "tcp", "host": "127.0.0.1", "port": 9, "interval": 3600}],
            admin_token=TOKEN))
        self.base, stop, self.app = start_app(cfg)
        self.addCleanup(stop)
        self.url = self.base + "/api/targets"

    def post(self, body, **kw):
        return request("POST", self.url, body=body, token=TOKEN, **kw)

    def status(self):
        return request("GET", self.base + "/status")[1]

    def by_name(self, name):
        return next((t for t in self.status()["targets"] if t["name"] == name), None)

    def test_add_http_and_tcp(self):
        s, body, _ = self.post(HTTP)
        self.assertEqual(s, 201)
        self.assertEqual((body["name"], body["source"], body["type"]), ("My site", "ui", "http"))
        self.assertIsInstance(body["id"], int)
        s, body2, _ = self.post(TCP)
        self.assertEqual(s, 201)
        t = self.by_name("DB")
        self.assertEqual((t["source"], t["port"], t["id"]), ("ui", 5432, body2["id"]))
        self.assertEqual(self.by_name("My site")["expected_status"], 200)

    def test_default_expected_status(self):
        d = dict(HTTP)
        del d["expected_status"]
        self.assertEqual(self.post(d)[1]["expected_status"], 200)

    def test_duplicates_409(self):
        self.post(HTTP)
        self.assertEqual(self.post(dict(HTTP, name="my SITE"))[0], 409)
        self.assertEqual(self.post(dict(TCP, name="CFGONE"))[0], 409)

    def test_validation_400_with_fields(self):
        cases = [
            (dict(HTTP, name=""), "name"), (dict(HTTP, name="x" * 65), "name"),
            (dict(HTTP, type="ping"), "type"), (dict(HTTP, url="ftp://x"), "url"),
            (dict(TCP, port=0), "port"), (dict(TCP, port=70000), "port"),
            (dict(HTTP, interval=4), "interval"), (dict(HTTP, expected_status=99), "expected_status"),
            (dict(HTTP, expected_status=600), "expected_status"), (dict(HTTP, extra=1), "extra"),
        ]
        d = dict(TCP)
        del d["host"]
        cases.append((d, "host"))
        for body, field in cases:
            s, resp, _ = self.post(body)
            self.assertEqual(s, 400, body)
            self.assertIn(field, resp["fields"])
            self.assertIn(field, resp["error"] + str(resp["fields"]))
        self.assertEqual(self.app.db.count_ui_targets(), 0)

    def test_limit_200(self):
        for i in range(200):
            self.app.db.add_ui_target(dict(TCP, name="t%d" % i), 1)
        s, body, _ = self.post(dict(TCP, name="one-too-many"))
        self.assertEqual(s, 409)
        self.assertIn("200", body["error"])

    def test_body_too_large_413(self):
        s, _, _ = self.post(None, raw=b"{" + b" " * 10300 + b"}")
        self.assertEqual(s, 413)

    def test_malformed_json_400(self):
        self.assertEqual(self.post(None, raw=b"{nope")[0], 400)
        self.assertEqual(self.post(None, raw=b"[1,2]")[0], 400)
        self.assertEqual(self.post(None, raw=b"")[0], 400)

    def test_edit(self):
        i = self.post(HTTP)[1]["id"]
        s, body, _ = request("PUT", "%s/%d" % (self.url, i), body=dict(HTTP, name="Renamed", interval=60), token=TOKEN)
        self.assertEqual(s, 200)
        self.assertEqual((body["name"], body["interval"]), ("Renamed", 60))
        t = self.by_name("Renamed")
        self.assertEqual(t["interval"], 60)
        self.assertIsNone(self.by_name("My site"))
        self.post(TCP)
        s, _, _ = request("PUT", "%s/%d" % (self.url, i), body=dict(HTTP, name="db"), token=TOKEN)
        self.assertEqual(s, 409)
        s, _, _ = request("PUT", "%s/%d" % (self.url, i), body=dict(HTTP, name="cfgone"), token=TOKEN)
        self.assertEqual(s, 409)
        s, _, _ = request("PUT", "%s/%d" % (self.url, i), body=dict(HTTP, name="Renamed"), token=TOKEN)
        self.assertEqual(s, 200)  # same name as itself is fine
        s, resp, _ = request("PUT", "%s/%d" % (self.url, i), body=dict(HTTP, interval=1), token=TOKEN)
        self.assertEqual(s, 400)

    def test_config_and_unknown_ids_404(self):
        cfg_id = self.by_name("cfgone")["id"]
        self.assertIsNone(cfg_id)
        for path in ("/999", "/abc", "/0"):
            self.assertEqual(request("PUT", self.url + path, body=HTTP, token=TOKEN)[0], 404)
            self.assertEqual(request("DELETE", self.url + path, token=TOKEN)[0], 404)
        self.assertEqual(request("PUT", self.url + "/999", body={"paused": True}, token=TOKEN)[0], 404)

    def test_pause_resume(self):
        i = self.post(HTTP)[1]["id"]
        u = "%s/%d" % (self.url, i)
        s, body, _ = request("PUT", u, body={"paused": True}, token=TOKEN)
        self.assertEqual((s, body["paused"]), (200, True))
        t = self.by_name("My site")
        self.assertEqual((t["state"], t["paused"]), ("paused", True))
        s, body, _ = request("PUT", u, body={"paused": False}, token=TOKEN)
        self.assertEqual(body["paused"], False)
        self.assertNotEqual(self.by_name("My site")["state"], "paused")
        self.assertEqual(request("PUT", u, body={"paused": "yes"}, token=TOKEN)[0], 400)

    def test_edit_keeps_paused_unless_given(self):
        i = self.post(HTTP)[1]["id"]
        u = "%s/%d" % (self.url, i)
        request("PUT", u, body={"paused": True}, token=TOKEN)
        request("PUT", u, body=dict(HTTP, interval=45), token=TOKEN)
        self.assertTrue(self.by_name("My site")["paused"])
        request("PUT", u, body=dict(HTTP, paused=False), token=TOKEN)
        self.assertFalse(self.by_name("My site")["paused"])

    def test_delete(self):
        i = self.post(HTTP)[1]["id"]
        self.assertEqual(request("DELETE", "%s/%d" % (self.url, i), token=TOKEN)[0], 204)
        self.assertIsNone(self.by_name("My site"))
        self.assertEqual(request("DELETE", "%s/%d" % (self.url, i), token=TOKEN)[0], 404)

    def test_unknown_api_path_404(self):
        self.assertEqual(request("GET", self.url)[0], 405)
        self.assertEqual(request("POST", self.url + "/1", body={}, token=TOKEN)[0], 405)
        self.assertEqual(request("PUT", self.url, body={}, token=TOKEN)[0], 405)


if __name__ == "__main__":
    unittest.main()
