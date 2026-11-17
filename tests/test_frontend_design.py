"""Shared page chrome, design tokens and self-hosted assets (#111)."""
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
CSS = (FRONTEND / "css" / "styles.css").read_text(encoding="utf-8")
NAV = {"./": "Restaurants", "create-restaurant.html": "Create a restaurant",
       "edit-restaurant.html": "Edit a restaurant"}
PAGES = {
    "index.html": "./", "create-restaurant.html": "create-restaurant.html",
    "edit-restaurant.html": "edit-restaurant.html", "restaurant.html": None, "menu-item.html": None,
}
TEXT_PAIRS = [
    ("ink", "paper"), ("muted", "paper"), ("accent", "paper"), ("danger", "paper"),
    ("success", "paper"), ("ink", "surface"), ("muted", "surface"), ("accent", "surface"),
    ("danger", "surface"), ("on-accent", "accent"), ("accent", "accent-soft"),
]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.links, self.ids, self.urls = [], [], set(), []
        self._link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append(tag)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        self.urls += [attrs[key] for key in ("href", "src") if attrs.get(key)]
        if tag == "a":
            self._link = {**attrs, "text": "", "in_nav": "nav" in self.stack,
                          "in_header": "header" in self.stack}
            self.links.append(self._link)

    def handle_endtag(self, tag):
        if tag in self.stack:
            del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]
        if tag == "a":
            self._link = None

    def handle_data(self, data):
        if self._link is not None:
            self._link["text"] += data


def parse(name):
    page = Page()
    page.feed((FRONTEND / name).read_text(encoding="utf-8"))
    return page


def tokens(pattern):
    match = re.search(pattern, CSS, re.S | re.M)
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", match.group(1))) if match else {}


def luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


LIGHT = tokens(r"^:root\s*\{(.*?)\}")
DARK = {**LIGHT, **tokens(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{(.*?)\}")}


@pytest.mark.parametrize("name,current", PAGES.items())
def test_every_page_shares_header_navigation_and_skip_link(name, current):
    page = parse(name)
    header = [link for link in page.links if link["in_header"]]
    assert header[0]["href"] == "#main" and header[0]["text"].strip() == "Skip to content"
    assert "main" in page.ids
    assert any(link["href"] == "./" and link["text"].strip() == "ByteBites" and not link["in_nav"]
               for link in header)
    nav = {link["href"]: link for link in header if link["in_nav"]}
    assert {href: link["text"].strip() for href, link in nav.items()} == NAV
    assert [href for href, link in nav.items() if link.get("aria-current") == "page"] == (
        [current] if current else [])


@pytest.mark.parametrize("scheme,palette", [("light", LIGHT), ("dark", DARK)])
@pytest.mark.parametrize("foreground,background", TEXT_PAIRS)
def test_text_tokens_meet_aa_contrast(scheme, palette, foreground, background):
    assert contrast(palette[foreground], palette[background]) >= 4.5


@pytest.mark.parametrize("scheme,palette", [("light", LIGHT), ("dark", DARK)])
def test_focus_ring_is_visible_against_page(scheme, palette):
    assert contrast(palette["focus"], palette["paper"]) >= 3


def test_focus_and_reduced_motion_are_styled():
    assert re.search(r":focus-visible\s*\{[^}]*outline:", CSS)
    assert "@media (prefers-reduced-motion: reduce)" in CSS


def test_assets_are_self_hosted():
    for name in PAGES:
        assert not [url for url in parse(name).urls if re.match(r"(https?:)?//", url)]
    fonts = re.findall(r"url\(\"?([^)\"]+)\"?\)", CSS)
    assert fonts and not [url for url in fonts if re.match(r"(https?:)?//", url)]
    for url in fonts:
        assert (FRONTEND / "css" / url).resolve().is_file()
    assert (FRONTEND / "fonts" / "OFL.txt").is_file()


def test_fonts_are_served_as_woff2(client):
    for url in re.findall(r"url\(\"?\.\./([^)\"]+)\"?\)", CSS):
        response = client.get(f"/app/{url}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "font/woff2"
