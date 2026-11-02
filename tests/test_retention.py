import unittest

from tests.helpers import make_db_path
from uptimewatch.db import Database

NOW = 1_800_000_000
DAY = 86400


class RetentionTests(unittest.TestCase):
    def setUp(self):
        path, cleanup = make_db_path()
        self.addCleanup(cleanup)
        self.db = Database(path)

    def test_prune(self):
        self.db.insert_result(NOW - 31 * DAY, "a", True, 1, "")
        self.db.insert_result(NOW - 30 * DAY, "a", True, 1, "")  # boundary kept
        self.db.insert_result(NOW - DAY, "a", True, 1, "")
        self.assertEqual(self.db.prune(30, NOW), 1)
        self.assertEqual(len(self.db.results_since("a", 0)), 2)
        self.assertEqual(self.db.prune(30, NOW), 0)


if __name__ == "__main__":
    unittest.main()
