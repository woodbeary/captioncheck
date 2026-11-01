"""Synchronicity: captions appear when the words are said, leave after, and can be read in time."""

from __future__ import annotations

import re
from statistics import median

from ..align import speech_span
from ..findings import FAIL, REVIEW, Finding
from ..context import Context


def _quote(text: str, n: int = 60) -> str:
    return f'"{text}"' if len(text) <= n else f'"{text[: n - 3]}..."'


def timing(ctx: Context) -> list[Finding]:
    cfg = ctx.config["sync"]
    out: list[Finding] = []
    for t in ctx.alignment.cues:
        cue = t.cue
        if t.n_tokens == 0:
            continue
        if t.heard_ratio < cfg["heard_ratio"]:
            if t.n_tokens >= cfg["unmatched_min_words"]:
                heard = " ".join(w.text for w in ctx.words
                                 if cue.start - 1 <= w.mid <= cue.end + 1)
                out.append(ctx.finding(
                    "synchronicity.unmatched_cue", REVIEW, cue.start, cue.end,
                    f"Only {t.heard} of {t.n_tokens} caption words were heard within "
                    f"{cfg['search_window_s']:g} s: {_quote(cue.text)}. Near it the speech model heard "
                    f"{_quote(heard) if heard else 'nothing'}. It may be on-screen text, a mishearing, "
                    f"or a caption far out of sync: a person should listen.",
                    cue=cue.index, measured={"heard": t.heard, "words": t.n_tokens}))
            continue
        span = speech_span(t, ctx.words, cfg["word_cap_s"])
        if span is None:
            continue
        s0, s1 = span
        p = sum(ctx.words[i].p for i in t.words) / len(t.words)
        sure = FAIL if p >= cfg["low_confidence_p"] else REVIEW
        late = cue.start - s0
        early_end = s1 - cue.end
        measured = {"caption_in_s": cue.start, "caption_out_s": cue.end, "speech_in_s": round(s0, 3),
                    "speech_out_s": round(s1, 3), "mean_word_p": round(p, 3)}
        if late > cfg["late_start_s"]:
            out.append(ctx.finding(
                "synchronicity.late_start", sure, s0, cue.start,
                f"Caption appears {late:.2f} s after the speech starts (limit {cfg['late_start_s']:g} s): "
                f"{_quote(cue.text)}.",
                cue=cue.index, measured={**measured, "offset_s": round(late, 3)}))
        elif -late > cfg["early_start_s"]:
            out.append(ctx.finding(
                "synchronicity.early_start", sure, cue.start, s0,
                f"Caption appears {-late:.2f} s before anyone says it (limit {cfg['early_start_s']:g} s): "
                f"{_quote(cue.text)}.",
                cue=cue.index, measured={**measured, "offset_s": round(late, 3)}))
        if early_end > cfg["early_end_s"]:
            out.append(ctx.finding(
                "synchronicity.early_end", sure, cue.end, s1,
                f"Caption leaves {early_end:.2f} s before the speech ends (limit {cfg['early_end_s']:g} s); "
                f"the end of the line is gone before it is said: {_quote(cue.text)}.",
                cue=cue.index, measured={**measured, "offset_s": round(-early_end, 3)}))
    return out


def _theil_sen(points: list[tuple[float, float]]) -> float:
    slopes = [(y2 - y1) / (x2 - x1) for i, (x1, y1) in enumerate(points)
              for x2, y2 in points[i + 1:] if x2 != x1]
    return median(slopes) if slopes else 0.0


def drift(ctx: Context) -> list[Finding]:
    """A caption offset that grows steadily, as timings made for another frame rate do."""
    cfg = ctx.config["sync"]
    points = []
    for t in ctx.alignment.cues:
        span = speech_span(t, ctx.words, cfg["word_cap_s"])
        if span and t.n_tokens and t.heard_ratio >= cfg["heard_ratio"]:
            points.append((t.cue.start, t.cue.start - span[0]))
    if len(points) < cfg["drift_min_cues"]:
        return []
    slope = _theil_sen(points)
    first, last = points[0][0], points[-1][0]
    change = slope * (last - first)
    per_min_ms = slope * 60_000
    if abs(per_min_ms) < cfg["drift_ms_per_min"] or abs(change) < cfg["late_start_s"]:
        return []
    return [ctx.finding(
        "synchronicity.drift", FAIL, first, last,
        f"Caption offset changes steadily by {per_min_ms:+.0f} ms per minute, {change:+.2f} s across "
        f"{len(points)} cues ({slope * 100:+.2f}% of elapsed time). A constant rate like this is how "
        f"captions timed for a different frame rate look; compare the caption file's frame rate with the program's.",
        measured={"ms_per_minute": round(per_min_ms, 1), "change_s": round(change, 3), "cues": len(points),
                  "ratio": round(1 + slope, 5)})]


def reading_rate(ctx: Context) -> list[Finding]:
    limit = ctx.config["reading"]["max_cps"]
    out = []
    for cue in ctx.cues:
        chars = cue.chars
        if cue.duration <= 0 or chars == 0:
            continue
        cps = chars / cue.duration
        if cps > limit:
            words = len(re.findall(r"\S+", cue.text))
            out.append(ctx.finding(
                "synchronicity.reading_rate", FAIL, cue.start, cue.end,
                f"{chars} characters in {cue.duration:.2f} s is {cps:.1f} characters per second "
                f"(limit {limit:g}); a reader gets {cue.duration:.2f} s for {_quote(cue.text)}.",
                cue=cue.index, models=[],
                measured={"chars": chars, "seconds": round(cue.duration, 3), "cps": round(cps, 2),
                          "wpm": round(words / cue.duration * 60, 1), "max_cps": limit}))
    return out
