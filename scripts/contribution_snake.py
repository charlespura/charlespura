"""Render a contribution snake using the same dated data as the profile charts.

The snake grows once per active day eaten along a collision-free calendar route.
After a brief hold, it fades out before the calendar and starting length reset.
Only presentation is animated; contribution dates and counts stay unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import escape
import math


BG = "#0B1220"
BORDER = "#23374B"
MUTED = "#94A3B8"
WHITE = "#F1F5F9"
SKY = "#38BDF8"
TEAL = "#2DD4BF"
LEVELS = ("#17283A", "#16455B", "#14778B", "#1CA6AA", "#2DD4BF")
SECONDS = 36
INITIAL_LENGTH = 7
MOVE_END = 82
FADE_START = 88
HIDDEN_AT = 94
RESET_AT = 96


def calendar_route(columns: int) -> list[tuple[int, int]]:
    """Return a closed unit-step route visiting every seven-row calendar cell.

    The first and last point coincide outside the calendar. All other points
    are unique. The animation uses the calendar traversal and first exit step.
    """
    if not isinstance(columns, int) or isinstance(columns, bool) or columns < 1:
        raise ValueError("Calendar must have at least one column")
    route = [(-1, 0)]
    for column in range(columns):
        rows = range(7) if column % 2 == 0 else range(6, -1, -1)
        route.extend((column, row) for row in rows)
    outside_row = 7 if columns % 2 else -1
    route.append((columns - 1, outside_row))
    route.extend((column, outside_row) for column in range(columns - 2, -2, -1))
    if outside_row == 7:
        route.extend((-1, row) for row in range(6, -1, -1))
    else:
        route.append((-1, 0))
    return route


@dataclass(frozen=True)
class SnakeFrame:
    """Head and tail indexes along the route, including the initial body."""

    head: int
    tail: int
    length: int
    ate: bool = False


def growth_frames(columns: int, food: set[tuple[int, int]]) -> tuple[list[tuple[int, int]], list[SnakeFrame]]:
    """Advance the head one cell per frame; retain the tail only when eating.

    Each active calendar day supplies one food square, regardless of its count.
    The initial body sits outside the calendar. No route position is revisited
    before the completed snake fades out, even when every square supplies food.
    """
    route = calendar_route(columns)
    if any(not (0 <= column < columns and 0 <= row < 7) for column, row in food):
        raise ValueError("Snake food must be inside the calendar")
    initial_tail = [(-1, row) for row in range(INITIAL_LENGTH - 1, 0, -1)]
    path = initial_tail + route[:columns * 7 + 2]
    tail = 0
    frames = [SnakeFrame(INITIAL_LENGTH - 1, tail, INITIAL_LENGTH)]
    for head in range(INITIAL_LENGTH, len(path)):
        ate = path[head] in food
        if not ate:
            tail += 1
        frames.append(SnakeFrame(head, tail, head - tail + 1, ate))
    return path, frames


def _turning_frames(values: list[tuple[int, int]]) -> list[int]:
    """Keep only changes of velocity, preserving exact linear motion."""
    selected = [0]
    for i in range(1, len(values) - 1):
        before = (values[i][0] - values[i - 1][0], values[i][1] - values[i - 1][1])
        after = (values[i + 1][0] - values[i][0], values[i + 1][1] - values[i][1])
        if before != after:
            selected.append(i)
    selected.append(len(values) - 1)
    return selected


def _text(x: float, y: float, label: object, size: int = 12, color: str = MUTED, **attrs: object) -> str:
    extra = " ".join(f'{key.replace("_", "-")}="{escape(str(value), quote=True)}"' for key, value in attrs.items())
    return f'<text x="{x:g}" y="{y:g}" fill="{color}" font-size="{size}" {extra}>{escape(str(label))}</text>'


def _validate(days: list, stamp: datetime) -> None:
    if not 30 <= len(days) <= 367:
        raise ValueError("Snake requires 30 to 367 consecutive contribution days")
    if not isinstance(stamp, datetime) or stamp.tzinfo is None:
        raise ValueError("Snake source timestamp must include a timezone")
    for day in days:
        if not isinstance(day.when, date) or isinstance(day.count, bool) or not isinstance(day.count, int) or day.count < 0:
            raise ValueError("Snake dates and counts must be valid")
        if isinstance(day.level, bool) or not isinstance(day.level, int) or not 0 <= day.level < len(LEVELS):
            raise ValueError("Snake contribution level must be between zero and four")
    if any(right.when - left.when != timedelta(days=1) for left, right in zip(days, days[1:])):
        raise ValueError("Snake contribution dates must be unique, sorted, and consecutive")
    if days[-1].when > stamp.astimezone(timezone.utc).date():
        raise ValueError("Snake calendar contains a future contribution date")


def render_snake(days: list, stamp: datetime) -> str:
    """Render an accessible animated SVG from objects with when/count/level.

    There are no network calls or output writes here. Unsupported animation
    and reduced-motion mode show the complete original contribution calendar.
    """
    _validate(days, stamp)
    stamp = stamp.astimezone(timezone.utc)
    first_sunday = days[0].when - timedelta(days=(days[0].when.weekday() + 1) % 7)
    columns = (days[-1].when - first_sunday).days // 7 + 1
    route = calendar_route(columns)
    indexes = {point: index for index, point in enumerate(route[:-1])}
    food = set()
    for day in days:
        if day.count:
            food.add(((day.when - first_sunday).days // 7, (day.when.weekday() + 1) % 7))
    path, frames = growth_frames(columns, food)
    movement_steps = len(frames) - 1
    step = min(26.0, 884 / columns)
    cell = step - 4
    x0 = (1000 - columns * step) / 2 + 2
    y0 = 108.0
    height = math.ceil(y0 + 7 * step + 66)
    total = sum(day.count for day in days)

    def center(point: tuple[int, int]) -> tuple[float, float]:
        return x0 + point[0] * step + cell / 2, y0 + point[1] * step + cell / 2

    def head_position(frame: SnakeFrame) -> str:
        x, y = center(path[frame.head])
        return f"transform:translate({x:.3f}px,{y:.3f}px)"

    # A single stroked route draws precisely the interval from tail to head.
    # Eating extends that interval while the tail holds; empty cells advance it.
    gap = len(path) * step * 2

    def body_position(frame: SnakeFrame) -> str:
        return f"stroke-dasharray:{(frame.length - 1) * step:.3f} {gap:.3f};stroke-dashoffset:{-frame.tail * step:.3f}"

    css = [
        f".snake-run{{animation:snake-loop {SECONDS}s linear infinite}}",
        f".snake-body{{animation:snake-grow {SECONDS}s linear infinite}}",
        f".snake-head{{animation:snake-move {SECONDS}s linear infinite}}",
        f"@keyframes snake-loop{{0%,{HIDDEN_AT}%,100%{{opacity:0}}2%,{FADE_START}%{{opacity:1}}}}",
    ]
    for name, values, position in (
        ("snake-move", [path[frame.head] for frame in frames], head_position),
        ("snake-grow", [(frame.length - 1, -frame.tail) for frame in frames], body_position),
    ):
        css.append(f"@keyframes {name}{{")
        for i in _turning_frames(values):
            css.append(f"{i / movement_steps * MOVE_END:.4f}%{{{position(frames[i])}}}")
        css.append(f"{HIDDEN_AT}%{{{position(frames[-1])}}}{RESET_AT}%,100%{{{position(frames[0])}}}}}")
    cells = []
    for i, day in enumerate(days):
        column = (day.when - first_sunday).days // 7
        row = (day.when.weekday() + 1) % 7
        eat_at = indexes[(column, row)] / movement_steps * MOVE_END
        color = LEVELS[day.level]
        animation = ""
        if day.count:
            css.append(f"@keyframes day-{i}{{0%,{eat_at:.4f}%{{fill:{color}}}{eat_at + 0.0001:.4f}%,{RESET_AT - 0.0001:.4f}%{{fill:{LEVELS[0]}}}{RESET_AT}%,100%{{fill:{color}}}}}")
            animation = f' style="animation:day-{i} {SECONDS}s steps(1,end) infinite"'
        cells.append(
            f'<rect class="calendar-day" x="{x0 + column * step:.3f}" y="{y0 + row * step:.3f}" width="{cell:.3f}" height="{cell:.3f}" rx="2.5" fill="{color}"{animation}><title>{day.when}: {day.count} contributions</title></rect>'
        )
    css.append("@media(prefers-reduced-motion:reduce){.calendar-day{animation:none!important}.snake-run{animation:none!important;opacity:0!important}.snake-piece{animation:none!important;opacity:0!important}}")

    description = (
        f"A cyan and teal snake travels through the real GitHub contribution calendar from {days[0].when} to {days[-1].when}. "
        f"The calendar contains {len(days)} days and {total:,} contributions. The snake starts with {INITIAL_LENGTH} segments and grows by one for each active day eaten, reaching {frames[-1].length} segments. Empty days do not add length. It fades out before resetting each loop. "
        f"Source as of {stamp.isoformat()}. Reduced-motion mode shows the complete static calendar."
    )
    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" fill="none" role="img" aria-labelledby="snake-title snake-description">',
        "<title id=\"snake-title\">GitHub contribution snake</title>",
        f'<desc id="snake-description">{escape(description)}</desc>',
        "<style>" + "\n".join(css) + "</style>",
        f'<rect x="0.5" y="0.5" width="999" height="{height - 1}" rx="18" fill="{BG}" stroke="{BORDER}"/>',
        '<g font-family="Segoe UI,Arial,sans-serif">',
        _text(30, 38, "CONTRIBUTION SNAKE", 13, SKY, font_weight=600, letter_spacing=1.7),
        _text(970, 38, f"Source as of {stamp:%Y-%m-%d %H:%M} UTC", 12, text_anchor="end"),
        _text(30, 66, f"{days[0].when:%d %b %Y} — {days[-1].when:%d %b %Y}", 13),
        _text(970, 66, f"{total:,} contributions · {len(days)} days", 13, TEAL, text_anchor="end"),
    ]
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        body.append(_text(x0 - step - 7, y0 + row * step + cell - 1, label, 10, text_anchor="end"))
    body.extend(cells)
    path_data = " ".join(f'{"M" if i == 0 else "L"}{center(point)[0]:.3f},{center(point)[1]:.3f}' for i, point in enumerate(path))
    initial_length = (INITIAL_LENGTH - 1) * step
    radius = min(4, cell / 3)
    eye = max(0.8, cell * 0.065)
    body.extend([
        '<g class="snake-run" opacity="0" aria-hidden="true">',
        f'<path class="snake-piece snake-body" d="{path_data}" fill="none" stroke="{SKY}" stroke-width="{cell - 1:.3f}" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{initial_length:.3f} {gap:.3f}" stroke-dashoffset="0"/>',
        '<g class="snake-piece snake-head">',
        f'<rect x="{-cell / 2:.3f}" y="{-cell / 2:.3f}" width="{cell:.3f}" height="{cell:.3f}" rx="{radius:.3f}" fill="{TEAL}" stroke="{WHITE}" stroke-opacity="0.5" stroke-width="1"/>',
        f'<circle cx="{-cell * 0.18:.3f}" cy="{-cell * 0.16:.3f}" r="{eye:.3f}" fill="{BG}"/>',
        f'<circle cx="{cell * 0.18:.3f}" cy="{-cell * 0.16:.3f}" r="{eye:.3f}" fill="{BG}"/>',
        '</g></g>',
    ])
    body.extend([
        _text(30, height - 21, "Each active square makes the snake longer.", 12),
        _text(970, height - 21, "CYAN / TEAL", 11, TEAL, text_anchor="end", letter_spacing=1),
        "</g></svg>\n",
    ])
    return "\n".join(body)
