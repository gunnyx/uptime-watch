import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from tests.helpers import TempDir, closed_port
from uptimewatch.cli import main
from uptimewatch.db import Database


class CliTests(unittest.TestCase):
    def setUp(self):
        self.t = TempDir()
        self.addCleanup(self.t.cleanup)
        os.environ.pop("UPTIME_ADMIN_TOKEN", None)
        self.db_path = self.t.file("x.db")

    def run_cli(self, cfg, *extra):
        p = self.t.file("c.json")
        with open(p, "w") as f:
            f.write(cfg if isinstance(cfg, str) else json.dumps(cfg))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["status", "--config", p] + list(extra))
        return code, out.getvalue(), err.getvalue()

    def cfg(self):
        return {"database": self.db_path, "targets": [
            {"name": "alpha", "type": "tcp", "host": "127.0.0.1", "port": closed_port()},
            {"name": "beta", "type": "tcp", "host": "127.0.0.1", "port": closed_port()}]}

    def test_table_columns_and_exit_one_when_down(self):
        db = Database(self.db_path)
        import time
        now = int(time.time())
        db.insert_result(now, "alpha", True, 3.2, "")
        db.insert_result(now, "beta", False, None, "refused")
        code, out, _ = self.run_cli(self.cfg())
        self.assertEqual(code, 1)
        for col in ("NAME", "SOURCE", "STATE", "LATENCY", "LAST CHECK", "24H"):
            self.assertIn(col, out)
        self.assertIn("alpha", out)
        self.assertRegex(out, r"beta\s+config\s+down")

    def test_exit_zero_when_all_up(self):
        db = Database(self.db_path)
        import time
        now = int(time.time())
        db.insert_result(now, "alpha", True, 3.2, "")
        db.insert_result(now, "beta", True, 1.0, "")
        code, out, _ = self.run_cli(self.cfg())
        self.assertEqual(code, 0)

    def test_unknown_not_down(self):
        code, out, _ = self.run_cli(self.cfg())
        self.assertEqual(code, 0)
        self.assertIn("unknown", out)

    def test_ui_targets_included(self):
        db = Database(self.db_path)
        import time
        db.add_ui_target({"name": "uit", "type": "tcp", "host": "h", "port": 1, "interval": 30}, 1)
        db.insert_result(int(time.time()), "uit", False, None, "x")
        code, out, _ = self.run_cli({"database": self.db_path})
        self.assertEqual(code, 1)
        self.assertRegex(out, r"uit\s+ui\s+down")

    def test_bad_config_exit_two(self):
        code, out, err = self.run_cli({"bogus": 1})
        self.assertEqual(code, 2)
        self.assertIn("bogus", err)
        code, _, err = self.run_cli("{bad")
        self.assertEqual(code, 2)

    def test_unreadable_db_exit_two(self):
        code, _, err = self.run_cli({"database": "/nonexistent-dir/q/x.db"})
        self.assertEqual(code, 2)
        self.assertTrue(err.strip())

    def test_missing_config_exit_two(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["status", "--config", self.t.file("none.json")])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
