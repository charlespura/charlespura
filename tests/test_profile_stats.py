"""Focused checks for source provenance, partial history, and safe output updates."""

from datetime import date, timedelta
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


SPEC = importlib.util.spec_from_file_location("profile_stats", Path(__file__).parents[1] / "scripts" / "update_profile_stats.py")
stats = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stats
SPEC.loader.exec_module(stats)


def snapshot():
    """Synthetic counts are confined to tests and never written to profile assets."""
    start = date(2026, 7, 9)
    return {
        "generated_at": "2026-10-28T02:39:36.073Z",
        "user": {"login": "charlespura", "repos": 88, "followers": 23, "following": 3},
        "range": {"from": "2025-10-26", "to": "2026-10-28"},
        "contributions": {"total": 2046},
        "streaks": {"current": {"days": 227}, "longest": {"days": 227}},
        "highlights": {"best_day": {"count": 50}},
        "heatmap": {"weeks": 16, "days": [
            {"date": str(start + timedelta(days=i)), "count": i % 6}
            for i in range(112)
        ]},
    }


class ProfileStatsTests(unittest.TestCase):
    def test_full_range_totals_and_streaks_are_not_recomputed_from_partial_history(self):
        data = snapshot()
        profile, source, days, stamp = stats.parse_snapshot(data)
        svg = stats.overview(profile, source, days, stamp)
        self.assertIn(">2,046</text>", svg)
        self.assertIn(">227 days</text>", svg)
        self.assertIn("26 Oct 2025", svg)
        self.assertIn("Source as of 2026-10-28 02:39 UTC", svg)
        self.assertEqual(len(days), 112)
        self.assertNotEqual(sum(day.count for day in days), data["contributions"]["total"])

    def test_graph_uses_exact_last_30_day_counts(self):
        _, _, days, stamp = stats.parse_snapshot(snapshot())
        svg = stats.recent_graph(days, stamp)
        total = sum(day.count for day in days[-30:])
        self.assertIn(f"{total} contributions ·", svg)
        self.assertIn(f"{days[-30].when}: {days[-30].count} contributions", svg)
        self.assertNotIn(f"{days[-31].when}: {days[-31].count} contributions", svg)

    def test_calendar_labels_available_history_instead_of_claiming_a_year(self):
        _, _, days, stamp = stats.parse_snapshot(snapshot())
        svg = stats.calendar_graph(days, stamp)
        self.assertIn("16 WEEKS", svg)
        self.assertIn("112 days", svg)
        self.assertNotIn("365", svg)

    def test_missing_duplicate_negative_and_future_daily_data_are_rejected(self):
        bad_cases = []
        data = snapshot()
        del data["heatmap"]["days"][30]
        bad_cases.append(data)
        data = snapshot()
        data["heatmap"]["days"][30]["date"] = data["heatmap"]["days"][29]["date"]
        bad_cases.append(data)
        data = snapshot()
        data["heatmap"]["days"][30]["count"] = -1
        bad_cases.append(data)
        data = snapshot()
        data["heatmap"]["days"][-1]["date"] = "2026-10-29"
        bad_cases.append(data)
        for data in bad_cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                stats.parse_snapshot(data)

    def test_bad_source_preserves_existing_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("github-stats.svg", "contribution-graph.svg", "contribution-calendar.svg"):
                (root / name).write_text("last good SVG", encoding="utf-8")
            data = snapshot()
            data["heatmap"]["days"] = []
            with self.assertRaises(ValueError):
                stats.generate(data, root)
            self.assertEqual([p.read_text() for p in root.glob("*.svg")], ["last good SVG"] * 3)

    def test_generated_svgs_parse_and_unchanged_snapshot_is_deterministic(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stats.generate(snapshot(), root)
            first = {p.name: p.read_bytes() for p in root.glob("*.svg")}
            self.assertEqual(len(first), 3)
            for content in first.values():
                svg = ET.fromstring(content)
                self.assertEqual(svg.attrib["role"], "img")
                self.assertTrue(svg.find("{http://www.w3.org/2000/svg}title").text)
                self.assertTrue(svg.find("{http://www.w3.org/2000/svg}desc").text)
            stats.generate(snapshot(), root)
            self.assertEqual(first, {p.name: p.read_bytes() for p in root.glob("*.svg")})

    def test_svg_text_is_escaped(self):
        fragment = stats.text(1, 2, '<unsafe> & "quoted"')
        parsed = ET.fromstring(fragment)
        self.assertEqual(parsed.text, '<unsafe> & "quoted"')


if __name__ == "__main__":
    unittest.main()
