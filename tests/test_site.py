"""Checks on the static site: every file the page needs exists and the head is complete.

Run with `python3 -m unittest`. Standard library only, so nothing needs installing.
Set SITE_DIR to check a different folder (used to test that these checks can fail).
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
        elif tag in ("title", "style"):
            self._in = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in ("title", "style"):
            self._in = ""

    def handle_data(self, data: str) -> None:
        if self._in == "title":
            self.title += data
        elif self._in == "style":
            self.style += data


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
        self.assertRegex(self.page.style, r"prefers-color-scheme\s*:\s*dark")


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
        self.assertNotRegex(self.page.style, r"url\(\s*['\"]?(https?:)?//|@import")

    def test_images_have_alt_text_and_one_h1(self) -> None:
        for tag, attrs in self.page.tags:
            if tag == "img":
                self.assertIn("alt", attrs, f"image {attrs.get('src')} has no alt attribute")
        self.assertEqual([t for t, _ in self.page.tags].count("h1"), 1)


if __name__ == "__main__":
    unittest.main()
