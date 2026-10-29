#!/usr/bin/env python3
"""Build local profile SVGs from the published GitHub Stats Generator JSON.

Live: python scripts/update_profile_stats.py
Saved snapshot: python scripts/update_profile_stats.py --input-json snapshot.json

Input is the existing gtihubstats stats.json schema: generated_at, user,
range, contributions.total, streaks, highlights.best_day, and heatmap.days.
No token or new third-party stats service is required. Counts are not estimated.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import math
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BG = "#0B1220"
PANEL = "#101C2D"
BORDER = "#23374B"
WHITE = "#F1F5F9"
MUTED = "#94A3B8"
SKY = "#38BDF8"
TEAL = "#2DD4BF"
LEVELS = ["#17283A", "#16455B", "#14778B", "#1CA6AA", "#2DD4BF"]

DEFAULT_SOURCE = "https://charlespura.github.io/gtihubstats/stats.json"


@dataclass(frozen=True)
class Day:
    when: date
    count: int
    level: int


def integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def fetch_snapshot(url: str) -> dict:
    if not url.startswith("https://"):
        raise ValueError("The published data source must use HTTPS")
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "charlespura-profile-stats",
    })
    try:
        with urlopen(request, timeout=45) as response:
            result = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"The stats source returned HTTP {error.code}; existing SVGs have been preserved") from None
    except URLError:
        raise RuntimeError("Could not reach the published stats source; existing SVGs have been preserved") from None
    if not isinstance(result, dict):
        raise ValueError("The stats source returned an unexpected response")
    return result


def parse_snapshot(snapshot: dict) -> tuple[dict, dict, list[Day], datetime]:
    profile = snapshot["user"]
    stamp = datetime.fromisoformat(snapshot["generated_at"].replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("generated_at must include a timezone")
    stamp = stamp.astimezone(timezone.utc)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", profile["login"]):
        raise ValueError("Invalid GitHub login")
    for field in ("repos", "followers", "following"):
        integer(profile[field], field)
    range_start = date.fromisoformat(snapshot["range"]["from"])
    range_end = date.fromisoformat(snapshot["range"]["to"])
    if range_end < range_start or range_end > stamp.date():
        raise ValueError("Invalid contribution range")
    integer(snapshot["contributions"]["total"], "contributions.total")
    for field in ("current", "longest"):
        integer(snapshot["streaks"][field]["days"], f"streaks.{field}.days")
    integer(snapshot["highlights"]["best_day"]["count"], "highlights.best_day.count")
    maximum = max(integer(raw["count"], "heatmap count") for raw in snapshot["heatmap"]["days"])
    days = []
    for raw in snapshot["heatmap"]["days"]:
        when = date.fromisoformat(raw["date"])
        count = integer(raw["count"], "heatmap count")
        # Shades indicate relative daily volume within this displayed calendar.
        level = min(4, math.ceil(count / maximum * 4)) if count else 0
        if not range_start <= when <= range_end:
            raise ValueError("Daily contribution date lies outside the source range")
        days.append(Day(when, count, level))
    days.sort(key=lambda day: day.when)
    if not 30 <= len(days) <= 367:
        raise ValueError("Expected a complete contribution calendar of 30 to 367 days")
    if any(right.when - left.when != timedelta(days=1) for left, right in zip(days, days[1:])):
        raise ValueError("Contribution dates must be unique and continuous; missing dates are not filled with guessed counts")
    if sum(day.count for day in days) > snapshot["contributions"]["total"]:
        raise ValueError("Daily history exceeds the source's full-range total")
    return profile, snapshot, days, stamp


def text(x: float, y: float, content: object, size: int = 15, color: str = MUTED, **attrs: object) -> str:
    extra = " ".join(f'{key.replace("_", "-")}="{escape(str(value), quote=True)}"' for key, value in attrs.items())
    return f'<text x="{x:g}" y="{y:g}" fill="{color}" font-size="{size}" {extra}>{escape(str(content))}</text>'


def frame(title: str, description: str, height: int, body: list[str]) -> str:
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" fill="none" role="img" aria-labelledby="title description">',
        f"<title id=\"title\">{escape(title)}</title>",
        f"<desc id=\"description\">{escape(description)}</desc>",
        f'<rect x="0.5" y="0.5" width="999" height="{height - 1}" rx="18" fill="{BG}" stroke="{BORDER}"/>',
        '<g font-family="Segoe UI, Arial, sans-serif">',
        *body,
        "</g></svg>\n",
    ])


def overview(profile: dict, snapshot: dict, days: list[Day], stamp: datetime) -> str:
    total = snapshot["contributions"]["total"]
    current = snapshot["streaks"]["current"]["days"]
    longest = snapshot["streaks"]["longest"]["days"]
    start = date.fromisoformat(snapshot["range"]["from"])
    end = date.fromisoformat(snapshot["range"]["to"])
    body = [
        text(30, 38, "GITHUB AT A GLANCE", 13, SKY, font_weight=600, letter_spacing=1.7),
        text(970, 38, f"Source as of {stamp:%Y-%m-%d %H:%M} UTC", 12, MUTED, text_anchor="end"),
        text(30, 75, f"@{profile['login']}", 23, WHITE, font_weight=600),
        text(30, 140, f"{total:,}", 55, WHITE, font_weight=700),
        text(30, 169, "contributions in this range", 15),
        text(30, 201, f"{start:%d %b %Y} — {end:%d %b %Y}", 12),
    ]
    tiles = [
        (f"{profile['repos']:,}", "Repositories"),
        (f"{profile['followers']:,}", "Followers"),
        (f"{profile['following']:,}", "Following"),
        (f"{current:,} days", "Current streak*"),
        (f"{longest:,} days", "Longest in range"),
        (f"{snapshot['highlights']['best_day']['count']:,}", "Best day"),
    ]
    for i, (value, label) in enumerate(tiles):
        x, y = 360 + (i % 3) * 204, 61 + (i // 3) * 91
        body.extend([
            f'<rect x="{x}" y="{y}" width="190" height="77" rx="10" fill="{PANEL}" stroke="{BORDER}"/>',
            text(x + 15, y + 27, label, 12),
            text(x + 15, y + 56, value, 24, TEAL if i in (3, 4) else WHITE, font_weight=600),
        ])
    body.append(text(30, 264, "*Streaks and totals follow the source range above. The graphs below show the available daily history.", 12))
    description = f"{profile['login']}: {total:,} contributions, {profile['repos']} repositories, {profile['followers']} followers. Range {start} to {end}. Current streak {current} days; longest streak in this range {longest} days. Source as of {stamp.isoformat()}."
    return frame("GitHub contribution overview", description, 286, body)


def recent_graph(days: list[Day], stamp: datetime) -> str:
    recent = days[-30:]
    total = sum(day.count for day in recent)
    peak = max(day.count for day in recent)
    ceiling = max(4, math.ceil(peak / 4) * 4)
    x0, y0, width, height = 64, 100, 904, 140
    body = [
        text(30, 38, "30 DAYS OF CONTRIBUTIONS", 13, SKY, font_weight=600, letter_spacing=1.7),
        text(970, 38, f"{total:,} contributions · {sum(day.count > 0 for day in recent)} active days", 13, TEAL, text_anchor="end"),
        text(30, 68, f"{recent[0].when:%d %b} — {recent[-1].when:%d %b %Y}", 13),
    ]
    for tick in range(5):
        y = y0 + height - tick * height / 4
        body.extend([
            f'<path d="M{x0} {y:g}H{x0 + width}" stroke="{BORDER}" stroke-dasharray="3 5"/>',
            text(x0 - 12, y + 4, ceiling * tick // 4, 11, text_anchor="end"),
        ])
    step = width / 30
    for i, day in enumerate(recent):
        bar_height = height * day.count / ceiling
        x = x0 + i * step + 3
        y = y0 + height - bar_height
        body.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{step - 6:.2f}" height="{max(2, bar_height):.2f}" rx="3" fill="{TEAL if i == 29 else SKY}" opacity="{1 if day.count else 0.18}"><title>{day.when}: {day.count} contributions</title></rect>')
        if i in (0, 7, 14, 21, 29):
            body.append(text(x + (step - 6) / 2, 265, f"{day.when:%d %b}", 11, text_anchor="middle"))
    body.extend([
        text(30, 303, "Daily totals from GitHub's contribution calendar; contributions include more than commits.", 12),
        text(970, 303, f"UTC · {stamp:%Y-%m-%d}", 11, text_anchor="end"),
    ])
    description = f"Daily contributions for {recent[0].when} through {recent[-1].when}. Total {total}; peak {peak} contributions in a day. " + "; ".join(f"{day.when}: {day.count}" for day in recent)
    return frame("Recent GitHub contribution activity", description, 324, body)


def calendar_graph(days: list[Day], stamp: datetime) -> str:
    start_sunday = days[0].when - timedelta(days=(days[0].when.weekday() + 1) % 7)
    columns = (days[-1].when - start_sunday).days // 7 + 1
    step = min(29, 560 / columns)
    cell = step - 4
    x0, y0 = 65, 97
    body = [
        text(30, 38, f"CONTRIBUTION CALENDAR · {len(days) // 7} WEEKS", 13, SKY, font_weight=600, letter_spacing=1.7),
        text(970, 38, f"{days[0].when:%d %b %Y} — {days[-1].when:%d %b %Y}", 12, text_anchor="end"),
    ]
    previous_month = None
    previous_label_x = -100
    for day in days:
        column = (day.when - start_sunday).days // 7
        row = (day.when.weekday() + 1) % 7
        x, y = x0 + column * step, y0 + row * step
        month = (day.when.year, day.when.month)
        if month != previous_month:
            # Avoid collisions if the range begins near a month boundary.
            if x - previous_label_x >= 40:
                body.append(text(x, 80, day.when.strftime("%b"), 11))
                previous_label_x = x
            previous_month = month
        body.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell:.2f}" height="{cell:.2f}" rx="2.5" fill="{LEVELS[day.level]}"><title>{day.when}: {day.count} contributions</title></rect>')
    for row, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        body.append(text(30, y0 + row * step + cell - 1, label, 11))
    body.extend([
        f'<rect x="660" y="97" width="310" height="190" rx="12" fill="{PANEL}" stroke="{BORDER}"/>',
        text(682, 127, "IN THIS CALENDAR", 12, MUTED, letter_spacing=1),
        text(682, 171, f"{sum(day.count for day in days):,}", 33, WHITE, font_weight=700),
        text(682, 196, "contributions", 14),
        text(682, 235, f"{sum(day.count > 0 for day in days)} active days", 18, TEAL, font_weight=600),
        text(682, 263, f"Peak: {max(day.count for day in days)} contributions / day", 13),
    ])
    body.append(text(30, 330, f"Daily history: {len(days)} days · Color intensity is relative to this calendar.", 12))
    body.append(text(789, 330, "Less", 11))
    for i, color in enumerate(LEVELS):
        body.append(f'<rect x="{825 + i * 18}" y="318" width="13" height="13" rx="2.5" fill="{color}"/>')
    body.append(text(923, 330, "More", 11))
    body.append(text(30, 360, "Activity follows GitHub's contribution calendar; scheduled automation may also count.", 12))
    description = f"GitHub contribution calendar from {days[0].when} to {days[-1].when}, with {sum(day.count for day in days):,} contributions. Each square represents one day; brighter squares indicate more activity. Updated {stamp.isoformat()}."
    return frame("GitHub contribution calendar", description, 384, body)


def generate(snapshot: dict, output_dir: Path) -> None:
    profile, collection, days, stamp = parse_snapshot(snapshot)
    rendered = {
        "github-stats.svg": overview(profile, collection, days, stamp),
        "contribution-graph.svg": recent_graph(days, stamp),
        "contribution-calendar.svg": calendar_graph(days, stamp),
    }
    # Fetch, validate and render everything before replacing any last-good asset.
    output_dir.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        for filename, content in rendered.items():
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", prefix=".profile-", suffix=".svg", dir=output_dir, delete=False) as handle:
                handle.write(content)
                staged.append((Path(handle.name), output_dir / filename))
        for temporary, target in staged:
            temporary.replace(target)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-url", default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=Path("assets"))
    parser.add_argument("--input-json", type=Path)
    args = parser.parse_args()
    try:
        if args.input_json:
            snapshot = json.loads(args.input_json.read_text(encoding="utf-8-sig"))
        else:
            snapshot = fetch_snapshot(args.source_url)
        generate(snapshot, args.output_dir)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as error:
        print(f"Profile stats update failed: {error}", file=sys.stderr)
        return 1
    print(f"Updated three profile SVGs in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
