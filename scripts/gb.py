"""Shared GameBoy drawing primitives for the profile SVGs.

Everything is on a 4px grid with crisp edges. Colors follow the DMG palette.
"""

from __future__ import annotations

import base64
from pathlib import Path

# DMG palette, darkest -> lightest
C0 = "#0f380f"
C1 = "#306230"
C2 = "#8bac0f"
C3 = "#9bbc0f"
BEZEL = "#c4bebb"
BEZEL_DARK = "#8b8b8b"
UA_BLUE = "#0057b7"
UA_YELLOW = "#ffd700"

FONT_PATH = Path(__file__).parent / "fonts" / "PressStart2P.subset.woff2"

WIDTH = 800


def font_face() -> str:
    if not FONT_PATH.exists():
        raise SystemExit(f"font missing: {FONT_PATH} (run fontTools.subset, see README)")
    b64 = base64.b64encode(FONT_PATH.read_bytes()).decode()
    return (
        "@font-face{font-family:'PS2P';src:url(data:font/woff2;base64,"
        + b64
        + ") format('woff2');}"
    )


BASE_CSS = """
text{font-family:'PS2P',monospace;fill:%s;}
.k{shape-rendering:crispEdges}
""" % C0


def svg(height: int, body: str, extra_css: str = "", title: str = "") -> str:
    """Wrap body in an SVG document with embedded font and screen bezel."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{title}">\n'
        f"<style>{font_face()}{BASE_CSS}{extra_css}</style>\n"
        f'<rect class="k" width="{WIDTH}" height="{height}" fill="{BEZEL}"/>\n'
        f'<rect class="k" x="8" y="8" width="{WIDTH-16}" height="{height-16}" fill="{BEZEL_DARK}"/>\n'
        f'<rect class="k" x="16" y="16" width="{WIDTH-32}" height="{height-32}" fill="{C3}"/>\n'
        f"{body}\n</svg>\n"
    )


def rect(x: int, y: int, w: int, h: int, fill: str, cls: str = "k", extra: str = "") -> str:
    return f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" {extra}/>'


def text(x: int, y: int, s: str, size: int = 16, fill: str = C0, extra: str = "") -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" {extra}>{s}</text>'


def frame(x: int, y: int, w: int, h: int) -> str:
    """Classic RPG dialogue frame: double border, light inside."""
    return "".join(
        [
            rect(x, y, w, h, C0),
            rect(x + 4, y + 4, w - 8, h - 8, C3),
            rect(x + 8, y + 8, w - 16, h - 16, C0),
            rect(x + 12, y + 12, w - 24, h - 24, C3),
        ]
    )


def bar(x: int, y: int, w: int, ratio: float, label: str, cls: str = "") -> str:
    """Labelled stat bar. ratio 0..1. Optional css class on the fill for animation."""
    ratio = max(0.0, min(1.0, ratio))
    inner = w - 8
    fill_w = int(round(inner * ratio / 4)) * 4
    out = [
        text(x, y + 14, label, 16),
        rect(x + 96, y, w, 20, C0),
        rect(x + 100, y + 4, inner, 12, C2),
    ]
    if fill_w > 0:
        out.append(rect(x + 100, y + 4, fill_w, 12, C0, cls=f"k {cls}" if cls else "k"))
    return "".join(out)


def pixels(x0: int, y0: int, rows: list[str], scale: int = 4, palette: dict[str, str] | None = None, extra: str = "") -> str:
    """Draw a sprite from text rows. Characters map to colors; '.' is transparent."""
    palette = palette or {"#": C0, "+": C1, "-": C2, "b": UA_BLUE, "y": UA_YELLOW}
    out = []
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            out.append(rect(x0 + i * scale, y0 + j * scale, scale, scale, palette[ch]))
    if extra:
        return f"<g {extra}>{''.join(out)}</g>"
    return "".join(out)


HERO_A = [
    "....####....",
    "...######...",
    "..##-##-##..",
    "..########..",
    "...##++##...",
    "....####....",
    "..########..",
    ".##+####+##.",
    ".##+####+##.",
    "..########..",
    "...##..##...",
    "..###..###..",
]

HERO_B = [
    "............",
    "....####....",
    "...######...",
    "..##-##-##..",
    "..########..",
    "...##++##...",
    "....####....",
    "..########..",
    ".##+####+##.",
    ".##+####+##.",
    "..########..",
    "..###..###..",
]

FLAG = [
    "bbbbbbbbbbbb",
    "bbbbbbbbbbbb",
    "bbbbbbbbbbbb",
    "yyyyyyyyyyyy",
    "yyyyyyyyyyyy",
    "yyyyyyyyyyyy",
]

HEART = [
    ".##.##.",
    "#######",
    "#######",
    ".#####.",
    "..###..",
    "...#...",
]


def hero(x: int, y: int, scale: int = 4) -> str:
    """Two-frame idle animation using CSS visibility toggling."""
    a = pixels(x, y, HERO_A, scale, extra='class="fa"')
    b = pixels(x, y, HERO_B, scale, extra='class="fb"')
    return a + b


HERO_CSS = """
.fa{animation:idleA 1s steps(1) infinite}
.fb{animation:idleB 1s steps(1) infinite}
@keyframes idleA{0%,50%{opacity:1}50.01%,100%{opacity:0}}
@keyframes idleB{0%,50%{opacity:0}50.01%,100%{opacity:1}}
"""
