"""Tests for grenn_visits.py. Run: python -m unittest test_grenn_visits (from this folder; standard library only)."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path

import grenn_visits as v

CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"


def line(day, path="/data/site_metrics.json", status=200, agent=CHROME, address="1.2.3.4", method="GET"):
    return f'{address} - - [{day}:10:00:00 +0800] "{method} {path} HTTP/2.0" {status} 512 "https://zerocarbonx.cn/cop31/" "{agent}"\n'


class VisitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def logs(self, current, rotated=""):
        (self.dir / "access.log").write_text(current, "utf-8")
        if rotated:
            with gzip.open(self.dir / "access.log.2.gz", "wt", encoding="utf-8") as handle:
                handle.write(rotated)
        return v.count_logs(str(self.dir / "access.log*"))

    def test_only_script_running_browsers_count(self):
        counted = self.logs(
            line("13/Nov/2026") + line("13/Nov/2026", status=304, address="5.6.7.8") + line("13/Nov/2026")
            + line("13/Nov/2026", path="/cop31/")                                   # the page itself: scanners fetch it too
            + line("13/Nov/2026", path="/data/dashboard.json")                      # asked for more than once a page
            + line("13/Nov/2026", agent="Mozilla/5.0 (X11) HeadlessChrome/141.0")   # our own tests
            + line("13/Nov/2026", agent="Mozilla/5.0 (compatible; Googlebot/2.1)")
            + line("13/Nov/2026", agent="curl/8.5.0") + line("13/Nov/2026", agent="-")
            + line("13/Nov/2026", status=404) + line("13/Nov/2026", method="HEAD")
            + line("13/Nov/2026", address="127.0.0.1")
            + "garbage line\n",
            rotated=line("12/Nov/2026", path="/data/site_metrics.json?v=1"))
        self.assertEqual(counted, {"2026-11-13": [3, 2], "2026-11-12": [1, 1]})

    def test_a_day_never_goes_down_and_old_days_are_kept(self):
        store = self.dir / "visits.json"
        v.update_store({"2026-11-01": [40, 9], "2026-11-02": [10, 4]}, store)
        days = v.update_store({"2026-11-02": [6, 2], "2026-11-03": [5, 5]}, store)   # 11-01 rotated away, 11-02 partly
        self.assertEqual(days, {"2026-11-01": [40, 9], "2026-11-02": [10, 4], "2026-11-03": [5, 5]})
        self.assertEqual(v.load_store(store), days)

    def test_series_adds_this_site_to_the_original_and_is_repeatable(self):
        metrics = self.dir / "site_metrics.json"
        upstream = [{"date": "2026-11-04", "value": 1970}, {"date": "2026-11-05", "value": 1980}, {"date": "2026-11-06", "value": 1980}]
        metrics.write_text(json.dumps({"visitor_cumulative": upstream, "notes": ["a"]}), "utf-8")
        days = {"2026-11-02": [10, 3], "2026-11-05": [20, 5], "2026-11-06": [5, 2], "2026-11-07": [1, 1]}  # 11-07: ahead of UTC
        first = v.apply(metrics, days)
        self.assertEqual((first["upstream"], first["site"], first["total"]), (1980, 36, 2016))
        saved = json.loads(metrics.read_text("utf-8"))
        self.assertEqual([p["value"] for p in saved["visitor_cumulative"]], [1980, 2010, 2016])
        self.assertEqual(saved["visitor_cumulative_upstream"], upstream)
        v.apply(metrics, days)
        again = json.loads(metrics.read_text("utf-8"))
        self.assertEqual(again["visitor_cumulative"], saved["visitor_cumulative"])
        self.assertEqual(len(again["notes"]), 2)

    def test_file_without_a_series_is_left_alone(self):
        metrics = self.dir / "site_metrics.json"
        metrics.write_text(json.dumps({"archive_cumulative": []}), "utf-8")
        self.assertFalse(v.apply(metrics, {"2026-11-02": [1, 1]})["applied"])
        self.assertEqual(json.loads(metrics.read_text("utf-8")), {"archive_cumulative": []})


if __name__ == "__main__":
    unittest.main()
