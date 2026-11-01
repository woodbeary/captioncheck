"""Caption line width in pixels on a target display, not in characters.

"42 characters" is a character count; a viewer sees pixels. "WWWWW" and
"iiiii" are both five characters, but in Arial-metric type the first is more
than four times wider. Width here is the sum of each glyph's measured advance width at the
display's caption font size, compared with the part of the screen captions may use.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources


@dataclass(frozen=True)
class GlyphTable:
    id: str
    units_per_em: int
    advances: dict[int, int]
    sha256: str

    def width_px(self, text: str, font_px: float) -> tuple[float, int]:
        """Width of text in px, and how many glyphs had no measured width.

        An unmeasured glyph counts as one full em: wide, so an overflow is not missed.
        """
        units, missing = 0, 0
        for ch in text:
            adv = self.advances.get(ord(ch))
            if adv is None:
                adv, missing = self.units_per_em, missing + 1
            units += adv
        return units * font_px / self.units_per_em, missing

    @property
    def model_ref(self) -> dict:
        return {"kind": "glyphs", "id": f"glyphs:{self.id}", "version": self.sha256[:16]}


@lru_cache(maxsize=None)
def glyph_table(table_id: str) -> GlyphTable:
    raw = resources.files("captioncheck").joinpath(f"data/glyphs/{table_id}.json").read_bytes()
    data = json.loads(raw)
    return GlyphTable(data["id"], data["units_per_em"], {int(k): v for k, v in data["advances"].items()},
                      hashlib.sha256(raw).hexdigest())


@dataclass(frozen=True)
class Display:
    id: str
    width_px: int
    usable_ratio: float
    font_px: float
    max_lines: int
    glyphs: str = "liberation-sans-regular"
    about: str = ""

    @property
    def usable_px(self) -> float:
        return self.width_px * self.usable_ratio


DISPLAYS = {
    "tv-1080p": Display(
        "tv-1080p", 1920, 0.80, 54, 2,
        about="1920 px wide; caption type 54 px (5% of 1080); lines kept to the central 80%. Assumed, not a spec."),
    "phone-large": Display(
        "phone-large", 390, 0.90, 18, 2,
        about="16:9 video across a 390 px phone held upright, with the reader's caption size turned up to 18 px."),
    "hud-488": Display(
        "hud-488", 488, 0.85, 21, 5,
        about="A 488 px monochrome glasses display at 21 px, 5 lines: the first display I measured glyphs for."),
}


def wrap(text: str, display: Display) -> list[str]:
    """Greedy word wrap to the display's usable width, as most caption renderers do."""
    table = glyph_table(display.glyphs)
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}" if current else word
        if not current or table.width_px(trial, display.font_px)[0] <= display.usable_px:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
