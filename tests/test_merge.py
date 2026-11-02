import unittest

from uptimewatch.targets import Target, merge_targets


def C(name):
    return Target(name=name, type="tcp", host="h", port=1, interval=30, source="config")


def U(id_, name, paused=0, updated=1):
    return {"id": id_, "name": name, "type": "http", "url": "http://x", "expected_status": 200,
            "host": None, "port": None, "interval": 30, "paused": paused, "updated_at": updated}


class MergeTests(unittest.TestCase):
    def test_union_sources_and_order(self):
        out, coll = merge_targets([C("a"), C("b")], [U(2, "z"), U(1, "y")])
        self.assertEqual([t.name for t in out], ["a", "b", "z", "y"])
        self.assertEqual([t.source for t in out], ["config", "config", "ui", "ui"])
        self.assertEqual(coll, [])
        self.assertEqual(out[2].id, 2)
        self.assertEqual(out[2].url, "http://x")

    def test_config_wins_case_insensitive_and_reported(self):
        out, coll = merge_targets([C("Site")], [U(1, "site"), U(2, "other")])
        self.assertEqual([t.name for t in out], ["Site", "other"])
        self.assertEqual(coll, ["site"])

    def test_paused_flagged_not_removed(self):
        out, _ = merge_targets([], [U(1, "p", paused=1)])
        self.assertTrue(out[0].paused)

    def test_config_never_paused_or_editable(self):
        out, _ = merge_targets([C("a")], [])
        self.assertFalse(out[0].paused)
        self.assertIsNone(out[0].id)

    def test_deleted_removed_and_edits_reflected(self):
        out, _ = merge_targets([], [U(1, "a", updated=5)])
        self.assertEqual(out[0].updated_at, 5)
        out, _ = merge_targets([], [])
        self.assertEqual(out, [])
        row = U(1, "renamed", updated=9)
        row["interval"] = 99
        out, _ = merge_targets([], [row])
        self.assertEqual((out[0].name, out[0].interval, out[0].updated_at), ("renamed", 99, 9))


if __name__ == "__main__":
    unittest.main()
