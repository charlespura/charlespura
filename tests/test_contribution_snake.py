"""Behavior checks for the real-data calendar animation and snake route."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import unittest
import xml.etree.ElementTree as ET

from scripts.contribution_snake import INITIAL_LENGTH, calendar_route, growth_frames, render_snake


@dataclass
class Day:
    when: date
    count: int
    level: int


def days_for(count=112, zero=False):
    start = date(2026, 7, 9)
    return [Day(start + timedelta(days=i), 0 if zero else i % 6, 0 if zero else min(i % 6, 4)) for i in range(count)]


class ContributionSnakeTests(unittest.TestCase):
    def test_eating_adds_one_segment_and_empty_cells_advance_the_tail(self):
        food = {(0, 0), (0, 3), (1, 6), (3, 2), (4, 6)}
        path, frames = growth_frames(5, food)
        self.assertEqual(frames[0].length, INITIAL_LENGTH)
        eaten = set()
        for previous, current in zip(frames, frames[1:]):
            coordinate = path[current.head]
            eating = coordinate in food
            if eating:
                eaten.add(coordinate)
            self.assertEqual(current.head, previous.head + 1)
            self.assertEqual(current.ate, eating)
            self.assertEqual(current.length, previous.length + int(eating))
            self.assertEqual(current.tail, previous.tail + int(not eating))
            body = path[current.tail:current.head + 1]
            self.assertEqual(len(body), INITIAL_LENGTH + len(eaten))
            self.assertEqual(len(body), len(set(body)), "The growing body must not overlap itself")
            for left, right in zip(body, body[1:]):
                self.assertEqual(abs(left[0] - right[0]) + abs(left[1] - right[1]), 1)
        self.assertEqual(eaten, food)
        self.assertEqual(frames[-1].length, INITIAL_LENGTH + len(food))

    def test_zero_activity_never_grows_and_dense_activity_has_no_length_cap(self):
        _, empty_frames = growth_frames(5, set())
        self.assertTrue(all(frame.length == INITIAL_LENGTH for frame in empty_frames))
        food = {(column, row) for column in range(54) for row in range(7)}
        _, dense_frames = growth_frames(54, food)
        self.assertEqual(dense_frames[-1].length, INITIAL_LENGTH + len(food))

    def test_growth_uses_active_squares_not_individual_contribution_counts(self):
        days = days_for(30, zero=True)
        days[4].count, days[4].level = 50, 4
        svg = render_snake(days, datetime(2026, 10, 28, tzinfo=timezone.utc))
        self.assertIn("reaching 8 segments", svg)
        self.assertIn("Empty days do not add length", svg)
        self.assertIn("@keyframes snake-grow", svg)
        self.assertIn("@keyframes snake-loop", svg)

    def test_route_is_closed_continuous_and_does_not_cross_itself(self):
        for columns in (5, 6, 17, 53, 54):
            with self.subTest(columns=columns):
                route = calendar_route(columns)
                self.assertEqual(route[0], route[-1])
                self.assertEqual(len(route[:-1]), len(set(route[:-1])))
                for left, right in zip(route, route[1:]):
                    self.assertEqual(abs(left[0] - right[0]) + abs(left[1] - right[1]), 1)
                visited = {point for point in route if 0 <= point[0] < columns and 0 <= point[1] < 7}
                self.assertEqual(visited, {(column, row) for column in range(columns) for row in range(7)})

    def test_calendar_preserves_real_dates_counts_and_partial_weeks(self):
        days = days_for()
        stamp = datetime(2026, 10, 28, tzinfo=timezone.utc)
        root = ET.fromstring(render_snake(days, stamp))
        cells = [node for node in root.iter() if node.get("class") == "calendar-day"]
        self.assertEqual(len(cells), len(days))
        titles = [node.find("{http://www.w3.org/2000/svg}title").text for node in cells]
        self.assertEqual(titles, [f"{day.when}: {day.count} contributions" for day in days])
        self.assertIn(f"{sum(day.count for day in days):,} contributions", root.find("{http://www.w3.org/2000/svg}desc").text)
        self.assertIn("112 days", "".join(root.itertext()))

    def test_zero_contributions_and_reduced_motion_keep_a_useful_calendar(self):
        svg = render_snake(days_for(zero=True), datetime(2026, 10, 28, tzinfo=timezone.utc))
        root = ET.fromstring(svg)
        cells = [node for node in root.iter() if node.get("class") == "calendar-day"]
        self.assertTrue(all(node.get("fill") == "#17283A" for node in cells))
        self.assertIn("prefers-reduced-motion:reduce", svg)
        self.assertIn(".calendar-day{animation:none!important}", svg)
        self.assertIn(".snake-piece{animation:none!important;opacity:0!important}", svg)
        self.assertNotIn("<script", svg)
        self.assertNotIn("foreignObject", svg)

    def test_full_history_stays_compact(self):
        days = days_for(367)
        svg = render_snake(days, datetime(2027, 7, 12, tzinfo=timezone.utc))
        ET.fromstring(svg)
        self.assertLess(len(svg.encode()), 150_000)

    def test_invalid_or_missing_history_is_rejected(self):
        stamp = datetime(2026, 10, 28, tzinfo=timezone.utc)
        for days in ([], days_for(29), list(reversed(days_for())), days_for() + [days_for()[-1]]):
            with self.subTest(days=len(days)), self.assertRaises(ValueError):
                render_snake(days, stamp)
        with self.assertRaises(ValueError):
            render_snake(days_for(), datetime(2026, 10, 28))


if __name__ == "__main__":
    unittest.main()
