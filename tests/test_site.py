"""Checks on the static site: every file the page needs exists and the head is complete.

Run with `python3 -m unittest discover -s tests`. Standard library only, so nothing needs
installing. Set SITE_DIR to check a different folder (used to test that these checks can fail).
"""

import os
import re
import struct
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(os.environ.get("SITE_DIR", Path(__file__).resolve().parent.parent))
DOMAIN = "tuppennywell.com"
SITE = f"https://{DOMAIN}"
MAX_PAGE_BYTES = 100_000  # the page should stay light
MAX_OG_IMAGE_BYTES = 5_000_000  # LinkedIn ignores preview images larger than 5 MB
MIN_CONTRAST = 4.5  # WCAG AA for normal text

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}


class Page(HTMLParser):
    """Collect the parts of the page the checks care about."""

    def __init__(self) -> None:
        super().__init__()
        self.lang = ""
        self.title = ""
        self.meta: dict[str, str] = {}
        self.links: list[dict[str, str]] = []
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.style = ""
        self.visible_text = ""
        self._stack: list[str] = []
        self._hidden_from: int | None = None  # stack depth where a hidden element starts
        self._in = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        self.tags.append((tag, a))
        if tag == "html":
            self.lang = a.get("lang") or ""
        elif tag == "meta":
            key = a.get("name") or a.get("property")
            if key:
                self.meta[key] = a.get("content") or ""
        elif tag == "link":
            self.links.append({k: v or "" for k, v in a.items()})
        # Only the page's own <title> counts, not the <title> inside an inline SVG.
        elif tag == "title" and "svg" not in self._stack:
            self._in = "title"
        elif tag == "style":
            self._in = "style"
        if tag not in VOID_TAGS:
            self._stack.append(tag)
            if "hidden" in a and self._hidden_from is None:
                self._hidden_from = len(self._stack)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("title", "style"):
            self._in = ""
        if tag in self._stack:
            while self._stack and self._stack.pop() != tag:
                pass
            if self._hidden_from is not None and len(self._stack) < self._hidden_from:
                self._hidden_from = None

    def handle_data(self, data: str) -> None:
        if self._in == "title":
            self.title += data
        elif self._in == "style":
            self.style += data
        elif self._hidden_from is None and not {"svg", "script", "style"} & set(self._stack):
            self.visible_text += data


def parse() -> Page:
    page = Page()
    page.feed((ROOT / "index.html").read_text(encoding="utf-8"))
    return page


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG file"
    return struct.unpack(">II", data[16:24])


def local_path(url: str) -> Path:
    """Map a link on the page (relative or on our own domain) to a file in the repo."""
    path = url.removeprefix(SITE).split("#")[0].split("?")[0]
    return ROOT / path.lstrip("/")


def all_css(page: Page) -> str:
    """The page's inline CSS plus every local stylesheet it links."""
    css = page.style
    for link in page.links:
        if link.get("rel") == "stylesheet" and not re.match(r"(https?:)?//", link["href"]):
            css += local_path(link["href"]).read_text(encoding="utf-8")
    return css


def luminance(colour: str) -> float:
    parts = [int(colour.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})", block))


class HeadTests(unittest.TestCase):
    page = parse()

    def test_language_and_viewport(self) -> None:
        self.assertTrue(self.page.lang.startswith("en"), "set <html lang=...>")
        self.assertIn("width=device-width", self.page.meta.get("viewport", ""))

    def test_title_and_description(self) -> None:
        self.assertTrue(10 <= len(self.page.title.strip()) <= 70, "title should be 10-70 characters")
        description = self.page.meta.get("description", "")
        self.assertTrue(50 <= len(description) <= 160, "description should be 50-160 characters")

    def test_canonical_and_open_graph(self) -> None:
        canonical = [x["href"] for x in self.page.links if x.get("rel") == "canonical"]
        self.assertEqual(canonical, [f"{SITE}/"])
        for key in ("og:title", "og:description", "og:type", "og:url", "og:image", "og:image:alt"):
            self.assertTrue(self.page.meta.get(key), f"missing {key}")
        self.assertEqual(self.page.meta["og:url"], f"{SITE}/")
        self.assertEqual(self.page.meta.get("twitter:card"), "summary_large_image")

    def test_supports_dark_mode(self) -> None:
        self.assertRegex(all_css(self.page), r"prefers-color-scheme\s*:\s*dark")


class FileTests(unittest.TestCase):
    page = parse()

    def test_link_preview_image(self) -> None:
        url = self.page.meta["og:image"]
        self.assertTrue(url.startswith(f"{SITE}/"), "og:image must be an absolute URL on the site")
        path = local_path(url)
        self.assertTrue(path.is_file(), f"{path.name} is missing")
        self.assertEqual(png_size(path), (1200, 630))
        self.assertLess(path.stat().st_size, MAX_OG_IMAGE_BYTES)
        self.assertEqual(self.page.meta.get("og:image:width"), "1200")
        self.assertEqual(self.page.meta.get("og:image:height"), "630")

    def test_icons(self) -> None:
        hrefs = {x["href"]: x for x in self.page.links if "icon" in x.get("rel", "")}
        for name in ("/favicon.svg", "/favicon.ico", "/apple-touch-icon.png"):
            self.assertIn(name, hrefs, f"page does not link {name}")
            self.assertTrue(local_path(name).is_file(), f"{name} is missing")
        self.assertIn(b"<svg", local_path("/favicon.svg").read_bytes())
        self.assertEqual(local_path("/favicon.ico").read_bytes()[:4], b"\x00\x00\x01\x00")
        self.assertEqual(png_size(local_path("/apple-touch-icon.png")), (180, 180))

    def test_linked_stylesheets_exist(self) -> None:
        for link in self.page.links:
            if link.get("rel") == "stylesheet":
                self.assertTrue(local_path(link["href"]).is_file(), f"{link['href']} is missing")

    def test_hosting_files(self) -> None:
        self.assertEqual((ROOT / "CNAME").read_text().strip(), DOMAIN)
        self.assertTrue((ROOT / ".nojekyll").is_file())

    def test_page_is_light(self) -> None:
        self.assertLess((ROOT / "index.html").stat().st_size, MAX_PAGE_BYTES)


class PrivacyAndAccessibilityTests(unittest.TestCase):
    page = parse()

    def test_no_scripts(self) -> None:
        scripts = [t for t, _ in self.page.tags if t == "script"]
        self.assertEqual(scripts, [], "the page is meant to need no JavaScript; update this test if that changes")

    def test_nothing_loads_from_other_sites(self) -> None:
        external = re.compile(r"^(https?:)?//", re.I)
        for tag, attrs in self.page.tags:
            for attr in ("src", "srcset", "data"):
                value = attrs.get(attr) or ""
                self.assertFalse(external.match(value), f"<{tag}> loads {value}")
        for link in self.page.links:
            if link.get("rel") != "canonical":
                self.assertFalse(external.match(link.get("href", "")), f"<link> loads {link}")
        self.assertNotRegex(all_css(self.page), r"url\(\s*['\"]?(https?:)?//|@import")

    def test_images_have_alt_text_and_one_h1(self) -> None:
        for tag, attrs in self.page.tags:
            if tag == "img":
                self.assertIn("alt", attrs, f"image {attrs.get('src')} has no alt attribute")
        self.assertEqual([t for t, _ in self.page.tags].count("h1"), 1)

    def test_no_placeholder_text_is_visible(self) -> None:
        found = re.findall(r"\[[A-Z][^\]\n]*\]", self.page.visible_text)
        self.assertEqual(found, [], "fill in or hide these placeholders before publishing")

    def test_text_contrast_meets_wcag_aa(self) -> None:
        css = all_css(self.page)
        light = tokens(re.search(r":root\s*\{(.*?)\}", css, re.S).group(1))
        dark_block = re.search(r"prefers-color-scheme\s*:\s*dark\s*\)\s*\{\s*:root\s*\{(.*?)\}", css, re.S)
        modes = {"light": light, "dark": {**light, **tokens(dark_block.group(1))}}
        pairs = [
            ("ink", "bg"), ("ink", "panel"), ("ink-soft", "bg"), ("ink-soft", "panel"),
            ("accent", "bg"), ("accent", "panel"), ("on-accent", "accent"),
        ]
        for mode, colours in modes.items():
            for fg, bg in pairs:
                ratio = contrast(colours[fg], colours[bg])
                self.assertGreaterEqual(ratio, MIN_CONTRAST, f"{mode}: {fg} on {bg} is only {ratio:.1f}:1")


if __name__ == "__main__":
    unittest.main()
