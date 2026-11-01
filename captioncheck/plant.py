"""Plant one known defect in a caption file, so a test can prove each check catches it.

Cue numbers are the file's own (1-based, in order). Each operation returns new
cues and leaves the input untouched.
"""

from __future__ import annotations

from dataclasses import replace

from .captions import Cue


def _pick(cues: list[Cue], n: int) -> Cue:
    for c in cues:
        if c.index == n:
            return c
    raise KeyError(f"no cue {n}")


def apply(cues: list[Cue], op: dict) -> list[Cue]:
    kind = op["op"]
    if kind == "drop":
        return [c for c in cues if c.index != op["cue"]]
    if kind == "shift":
        lo, hi = op["cues"]
        return [replace(c, start=c.start + op["by"], end=c.end + op["by"]) if lo <= c.index <= hi else c
                for c in cues]
    if kind == "merge":
        a, b = _pick(cues, op["cues"][0]), _pick(cues, op["cues"][1])
        merged = replace(a, lines=(a.text, b.text))
        return [merged if c.index == a.index else c for c in cues if c.index != b.index]
    if kind == "join_lines":
        return [replace(c, lines=(c.text,)) if c.index == op["cue"] else c for c in cues]
    if kind == "scale":
        f, o = op["factor"], op["origin"]
        return [replace(c, start=o + (c.start - o) * f, end=o + (c.end - o) * f) if c.start >= o else c
                for c in cues]
    if kind == "add_cue":
        start, end = op["at"]
        added = Cue(index=0, start=start, end=end, lines=(op["text"],))
        return sorted(cues + [added], key=lambda c: c.start)
    raise ValueError(f"unknown plant {kind}")
