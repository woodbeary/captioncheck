"""Completeness: speech with no caption on screen.

A hearing reviewer rarely notices a missing line, because they heard it. A
Deaf viewer loses it. A heard word counts as captioned when the alignment tied
it to a caption, or when any caption is on screen while it is said.
"""

from __future__ import annotations

from ..findings import FAIL, REVIEW, Finding
from ..context import Context


def uncaptioned_speech(ctx: Context) -> list[Finding]:
    cfg = ctx.config["completeness"]
    tol = cfg["on_screen_tolerance_s"]

    def on_screen(t: float) -> bool:
        return any(c.start - tol <= t <= c.end + tol for c in ctx.cues)

    runs: list[list[int]] = []
    for i, w in enumerate(ctx.words):
        if ctx.alignment.word_cue[i] is not None or on_screen(w.mid):
            continue
        if runs and w.start - ctx.words[runs[-1][-1]].end <= cfg["join_gap_s"]:
            runs[-1].append(i)
        else:
            runs.append([i])

    out = []
    for run in runs:
        if len(run) < cfg["min_words"]:
            continue
        ws = [ctx.words[i] for i in run]
        start, end = ws[0].start, max(w.end_within(ctx.config["sync"]["word_cap_s"]) for w in ws)
        heard = " ".join(w.text for w in ws)
        p = sum(w.p for w in ws) / len(ws)
        level = ctx.audio.level_dbfs(start, end)
        sure = p >= cfg["low_confidence_p"] and level >= cfg["min_level_dbfs"]
        note = "" if sure else (
            f" Confidence is low (mean word p {p:.2f}, level {level:.1f} dBFS), so the model may have "
            f"imagined it: a person should listen.")
        out.append(ctx.finding(
            "completeness.uncaptioned_speech", FAIL if sure else REVIEW, start, end,
            f"Speech with no caption on screen for {end - start:.2f} s. The speech model heard "
            f'"{heard}" ({len(ws)} words). A Deaf viewer gets nothing here.{note}',
            measured={"words": len(ws), "mean_word_p": round(p, 3), "level_dbfs": round(level, 1),
                      "heard": heard}))
    return out
