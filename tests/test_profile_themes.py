"""Check fixed README themes, preserved animations, and offline rebuilding."""

from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from scripts.profile_palette import PROFILE_GRAPHICS, THEME_CSS, build_themes, render_theme


ROOT = Path(__file__).resolve().parents[1]
SVG = "{http://www.w3.org/2000/svg}"


class Pictures(HTMLParser):
    def __init__(self):
        super().__init__()
        self.pictures = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "picture":
            self.current = []
        elif self.current is not None:
            self.current.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag == "picture":
            self.pictures.append(self.current)
            self.current = None


class ProfileThemeTests(unittest.TestCase):
    def test_fixed_themes_preserve_layout_data_and_animation(self):
        for filename in PROFILE_GRAPHICS:
            source = (ROOT / "assets" / filename).read_text(encoding="utf-8")
            original = ET.fromstring(source)
            for theme, background, foreground in (
                ("light", "#F4F4F1", "#101114"),
                ("dark", "#0B0D10", "#F4F4F2"),
            ):
                with self.subTest(filename=filename, theme=theme):
                    rendered = render_theme(source, theme)
                    themed = ET.fromstring(rendered)
                    self.assertEqual(original.attrib, themed.attrib)
                    self.assertEqual(original.find(f"{SVG}title").text, themed.find(f"{SVG}title").text)
                    self.assertEqual(original.find(f"{SVG}desc").text, themed.find(f"{SVG}desc").text)
                    self.assertIn(background, rendered)
                    self.assertIn(foreground, rendered)
                    self.assertNotIn("prefers-color-scheme", rendered)
                    for tag in ("rect", "path", "text", "circle", "g", "stop"):
                        old = list(original.iter(f"{SVG}{tag}"))
                        new = list(themed.iter(f"{SVG}{tag}"))
                        self.assertEqual(len(old), len(new))
                        for left, right in zip(old, new):
                            for key, value in left.attrib.items():
                                if key not in ("fill", "stroke", "stop-color"):
                                    self.assertEqual(right.get(key), value)
                            self.assertEqual(left.text, right.text)
                    old_styles = "".join(node.text or "" for node in original.iter(f"{SVG}style")).replace(THEME_CSS, "")
                    new_styles = "".join(node.text or "" for node in themed.iter(f"{SVG}style"))
                    def without_colors(css):
                        return re.sub(r"(?<=fill:)(?:var\(--[a-z0-9]+\)|#[0-9A-Fa-f]{6})", "COLOR", css).strip()
                    self.assertEqual(without_colors(old_styles), without_colors(new_styles))

    def test_offline_rebuild_preserves_sources_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = Path(directory)
            originals = {}
            for filename in PROFILE_GRAPHICS:
                originals[filename] = (ROOT / "assets" / filename).read_bytes()
                (assets / filename).write_bytes(originals[filename])
            self.assertEqual(build_themes(assets), 12)
            first = {path.relative_to(assets): path.read_bytes() for path in assets.rglob("*.svg")}
            for filename, content in originals.items():
                self.assertEqual((assets / filename).read_bytes(), content)
            build_themes(assets)
            self.assertEqual(first, {path.relative_to(assets): path.read_bytes() for path in assets.rglob("*.svg")})

    def test_readme_selects_existing_fixed_images_for_both_themes(self):
        parser = Pictures()
        parser.feed((ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(len(parser.pictures), len(PROFILE_GRAPHICS))
        for picture in parser.pictures:
            sources = {attrs["media"]: attrs["srcset"] for tag, attrs in picture if tag == "source"}
            image = next(attrs for tag, attrs in picture if tag == "img")
            filename = Path(image["src"]).name
            self.assertIn(filename, PROFILE_GRAPHICS)
            self.assertTrue(image.get("alt"))
            for theme in ("light", "dark"):
                path = f"./assets/themes/{theme}/{filename}"
                self.assertEqual(sources[f"(prefers-color-scheme: {theme})"], path)
                self.assertTrue((ROOT / path).is_file())
            self.assertEqual(image["src"], f"./assets/themes/light/{filename}")


if __name__ == "__main__":
    unittest.main()
