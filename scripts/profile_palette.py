"""Monochrome SVG colors matching the portfolio's light and dark themes."""

import argparse
from pathlib import Path
import re


PROFILE_GRAPHICS = (
    "charles-pura-banner.svg",
    "developer-intro.svg",
    "github-stats.svg",
    "contribution-graph.svg",
    "contribution-calendar.svg",
    "contribution-snake.svg",
)


DARK = {
    "bg": "#0B0D10",
    "panel": "#111419",
    "soft": "#181C22",
    "text": "#F4F4F2",
    "muted": "#A6ABB4",
    "detail": "#D8DADE",
    "line": "rgba(255,255,255,0.13)",
    "edge": "rgba(255,255,255,0.3)",
    "l0": "#181C22",
    "l1": "#3B3F46",
    "l2": "#656971",
    "l3": "#A6ABB4",
    "l4": "#F4F4F2",
    "s0": "#F4F4F2",
    "s1": "#D8DADE",
    "s2": "#C5C8CD",
    "s3": "#A6ABB4",
    "s4": "#92969E",
    "s5": "#737984",
    "s6": "#656971",
}

LIGHT = {
    "bg": "#F4F4F1",
    "panel": "#FFFFFF",
    "soft": "#F0F0ED",
    "text": "#101114",
    "muted": "#656971",
    "detail": "#656971",
    "line": "rgba(16,17,20,0.14)",
    "edge": "rgba(16,17,20,0.3)",
    "l0": "#F0F0ED",
    "l1": "#C5C8CD",
    "l2": "#92969E",
    "l3": "#656971",
    "l4": "#101114",
    "s0": "#101114",
    "s1": "#282A30",
    "s2": "#41454D",
    "s3": "#656971",
    "s4": "#737984",
    "s5": "#92969E",
    "s6": "#A6ABB4",
}


def color(name: str) -> str:
    return f"var(--{name})"


def _declarations(palette: dict[str, str]) -> str:
    return ";".join(f"--{name}:{value}" for name, value in palette.items())


# Short level names keep the full-year snake below its SVG size limit.
THEME_CSS = (
    ":root{" + _declarations(DARK) + "}"
    "@media(prefers-color-scheme:light){:root{" + _declarations(LIGHT) + "}}"
)

BG = color("bg")
PANEL = color("panel")
BORDER = color("line")
TEXT = color("text")
MUTED = color("muted")
ACCENT = MUTED
HIGHLIGHT = TEXT
LEVELS = tuple(color(f"l{level}") for level in range(5))
SNAKE_COLORS = tuple(color(f"s{segment}") for segment in range(7))


def render_theme(svg: str, theme: str) -> str:
    """Fix an SVG's palette so a README picture source controls its theme."""
    palette = {"light": LIGHT, "dark": DARK}[theme]
    if THEME_CSS not in svg:
        raise ValueError("Profile SVG is missing its shared theme palette")
    svg = svg.replace(THEME_CSS, "")
    svg = re.sub(
        r"var\(--([a-z0-9-]+)\)",
        lambda match: palette.get(match[1], match[0]),
        svg,
    )
    return re.sub(r"<style>\s*</style>\n?", "", svg)


def theme_variants(filename: str, svg: str) -> dict[str, str]:
    return {
        f"themes/{theme}/{filename}": render_theme(svg, theme)
        for theme in ("light", "dark")
    }


def build_themes(assets_dir: Path) -> int:
    """Build checked-in artwork variants offline, without changing stats."""
    rendered = {}
    for filename in PROFILE_GRAPHICS:
        svg = (assets_dir / filename).read_text(encoding="utf-8")
        rendered.update(theme_variants(filename, svg))
    for filename, svg in rendered.items():
        target = assets_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg, encoding="utf-8", newline="\n")
    return len(rendered)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild light and dark profile artwork from the existing SVGs.")
    parser.add_argument("--assets-dir", type=Path, default=Path("assets"))
    arguments = parser.parse_args()
    print(f"Updated {build_themes(arguments.assets_dir)} light/dark SVGs in {arguments.assets_dir}")
