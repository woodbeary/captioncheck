"""Placement: every line fits the target display, measured in pixels per glyph."""

from __future__ import annotations

from ..findings import FAIL, Finding
from ..context import Context
from ..layout import glyph_table, wrap


def line_fit(ctx: Context) -> list[Finding]:
    out = []
    for display_id in ctx.config["placement"]["displays"]:
        d = ctx.config.displays[display_id]
        table = glyph_table(d.glyphs)
        for cue in ctx.cues:
            lines = [line for line in cue.display_lines if line]
            if not lines:
                continue
            measured = [table.width_px(line, d.font_px) for line in lines]
            widths = [round(w, 1) for w, _ in measured]
            unmeasured = sum(m for _, m in measured)
            base = {"display": d.id, "usable_px": round(d.usable_px, 1), "font_px": d.font_px,
                    "line_px": widths, "line_chars": [len(line) for line in lines],
                    "unmeasured_glyphs": unmeasured}
            widest = max(range(len(lines)), key=lambda i: widths[i])
            if widths[widest] > d.usable_px:
                out.append(ctx.finding(
                    "placement.line_width", FAIL, cue.start, cue.end,
                    f"On {d.id}, line {widest + 1} is {widths[widest]:.0f} px wide at {d.font_px:g} px type "
                    f"({len(lines[widest])} characters); captions there may use {d.usable_px:.0f} px. "
                    f"The player will break it where the author didn't, or it runs off the screen.",
                    cue=cue.index, models=[table.model_ref], measured=base))
            rendered = sum(len(wrap(line, d)) for line in lines)
            if rendered > d.max_lines:
                out.append(ctx.finding(
                    "placement.line_count", FAIL, cue.start, cue.end,
                    f"On {d.id}, this caption needs {rendered} lines (limit {d.max_lines}) once it is "
                    f"wrapped to {d.usable_px:.0f} px, covering more of the picture.",
                    cue=cue.index, models=[table.model_ref], measured={**base, "rendered_lines": rendered}))
    return out
