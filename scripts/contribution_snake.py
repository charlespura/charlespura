"""Render a contribution snake using the same dated data as the profile charts.

The snake follows a continuous, collision-free route through calendar cells.
It returns outside the calendar while the consumed cells reset for the next lap.
Only presentation is animated; contribution dates and counts stay unchanged.
"""

from __future__ import annotations

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
TAIL_LENGTH = 6


def calendar_route(columns: int) -> list[tuple[int, int]]:
    """Return a closed unit-step route visiting every seven-row calendar cell.

    The first and last point coincide outside the calendar. All other points
    are unique, so the six-piece tail cannot cross itself on supported grids.
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
    cycle_steps = len(route) - 1
    indexes = {point: index for index, point in enumerate(route[:-1])}
    step = min(26.0, 884 / columns)
    cell = step - 4
    x0 = (1000 - columns * step) / 2 + 2
    y0 = 108.0
    height = math.ceil(y0 + 7 * step + 66)
    # By this point the head and entire tail are on the exterior corridor.
    restore_at = (columns * 7 + TAIL_LENGTH + 2) / cycle_steps * 100
    restore_at = min(restore_at, 99.0)
    total = sum(day.count for day in days)

    css = [
        ".snake-piece{opacity:0;animation:snake-move 36s linear infinite}",
        "@keyframes snake-move{",
    ]
    for i, (column, row) in enumerate(route):
        x, y = x0 + column * step, y0 + row * step
        css.append(f"{i / cycle_steps * 100:.4f}%{{transform:translate({x:.3f}px,{y:.3f}px);opacity:1}}")
    css.append("}")
    cells = []
    for i, day in enumerate(days):
        column = (day.when - first_sunday).days // 7
        row = (day.when.weekday() + 1) % 7
        eat_at = indexes[(column, row)] / cycle_steps * 100
        color = LEVELS[day.level]
        css.append(f"@keyframes day-{i}{{0%,{eat_at:.4f}%{{fill:{color}}}{eat_at + 0.0001:.4f}%,{restore_at:.4f}%{{fill:{LEVELS[0]}}}{restore_at + 0.0001:.4f}%,100%{{fill:{color}}}}}")
        cells.append(
            f'<rect class="calendar-day" x="{x0 + column * step:.3f}" y="{y0 + row * step:.3f}" width="{cell:.3f}" height="{cell:.3f}" rx="2.5" fill="{color}" style="animation:day-{i} {SECONDS}s steps(1,end) infinite"><title>{day.when}: {day.count} contributions</title></rect>'
        )
    css.append("@media(prefers-reduced-motion:reduce){.calendar-day{animation:none!important}.snake-piece{animation:none!important;opacity:0!important}}")

    description = (
        f"A cyan and teal snake travels through the real GitHub contribution calendar from {days[0].when} to {days[-1].when}. "
        f"The calendar contains {len(days)} days and {total:,} contributions. Squares are consumed for the animation and restored each loop. "
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
    # Negative phase offsets keep the tail behind the head from the first lap.
    colors = (TEAL, "#2CCEC2", "#2CC6CF", "#30B9E1", SKY, "#2686AE", "#1D607D")
    for segment in range(TAIL_LENGTH, -1, -1):
        delay = -SECONDS + segment * SECONDS / cycle_steps if segment else 0
        stroke = f' stroke="{WHITE}" stroke-opacity="0.5" stroke-width="1"' if not segment else ""
        body.append(
            f'<g class="snake-piece" opacity="0" style="animation-delay:{delay:.6f}s" aria-hidden="true"><rect width="{cell:.3f}" height="{cell:.3f}" rx="{min(4, cell / 3):.3f}" fill="{colors[segment]}"{stroke}/></g>'
        )
    body.extend([
        _text(30, height - 21, "A little play, built from real contribution history.", 12),
        _text(970, height - 21, "CYAN / TEAL", 11, TEAL, text_anchor="end", letter_spacing=1),
        "</g></svg>\n",
    ])
    return "\n".join(body)
