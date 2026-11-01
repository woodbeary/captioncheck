"""Sound and tone a Deaf viewer can't hear, flagged for a person and never written by captioncheck.

Captions say what was said; they often don't say that a door slammed or that a
line was shouted. These checks find where the audio carries something no
caption mentions. Naming the sound, or the tone, is a person's job: a label
written by a tool that only measured loudness would be a guess shown as fact.
"""

from __future__ import annotations

import numpy as np

from ..align import speech_span
from ..audio import envelope_dbfs
from ..findings import REVIEW, Finding
from ..context import Context

HOP = 0.01


def _rolling_background(db: np.ndarray, frames: int) -> np.ndarray:
    """Median level of the frames just before each frame (fewer at the very start)."""
    bg = np.empty_like(db)
    bg[0] = db[0]
    for i in range(1, len(db)):
        bg[i] = float(np.median(db[max(0, i - frames):i]))
    return bg


def _labelled_near(ctx: Context, start: float, end: float, reach: float) -> bool:
    return any(c.labels and c.start <= end + reach and c.end >= start - reach for c in ctx.cues)


def unlabelled_sound(ctx: Context) -> list[Finding]:
    cfg = ctx.config["sound"]
    source = ctx.me or ctx.audio
    times, db = envelope_dbfs(source, hop=HOP)
    if len(db) == 0:
        return []
    db = db.copy()
    if ctx.me is None:
        guard = cfg["speech_guard_s"]
        for w in ctx.words:
            db[(times >= w.start - guard) & (times <= w.end + guard)] = -120.0
    bg = _rolling_background(db, int(cfg["background_s"] / HOP))
    hot = (db >= cfg["min_dbfs"]) & (db - bg >= cfg["rise_db"])

    events: list[list[int]] = []
    for i in np.flatnonzero(hot):
        if events and (times[i] - times[events[-1][-1]]) <= cfg["merge_gap_s"]:
            events[-1].append(int(i))
        else:
            events.append([int(i)])

    where = "the music-and-effects stem" if ctx.me else "the mix, outside speech"
    out = []
    for ev in events:
        start, end = float(times[ev[0]] - HOP / 2), float(times[ev[-1]] + HOP / 2)
        if end - start < cfg["min_event_s"] or _labelled_near(ctx, start, end, cfg["label_reach_s"]):
            continue
        peak = float(db[ev].max())
        rise = float((db[ev] - bg[ev]).max())
        measured = {"peak_dbfs": round(peak, 1), "rise_db": round(rise, 1), "seconds": round(end - start, 2),
                    "measured_on": where}
        if ctx.me is not None:
            measured["me_span_sha256"] = ctx.me.span_sha256(start, end)
        out.append(ctx.finding(
            "accuracy.unlabelled_sound", REVIEW, start, end,
            f"A sound rises {rise:.0f} dB above the {cfg['background_s']:g} s before it (peak {peak:.1f} dBFS "
            f"in {where}) and no caption near it labels a sound. Listen. If a Deaf viewer needs it, write "
            f"the label; captioncheck does not.",
            measured=measured))
    return out


def unmarked_tone(ctx: Context) -> list[Finding]:
    """Lines spoken far louder or quieter than this program's usual line, with nothing marking it."""
    cfg = ctx.config["tone"]
    heard_ratio = ctx.config["sync"]["heard_ratio"]
    spans = []
    for t in ctx.alignment.cues:
        span = speech_span(t, ctx.words, ctx.config["sync"]["word_cap_s"])
        if span and t.n_tokens and t.heard_ratio >= heard_ratio:
            spans.append((t.cue, span, ctx.audio.level_dbfs(*span)))
    if len(spans) < 3:
        return []
    typical = float(np.median([lvl for _, _, lvl in spans]))
    out = []
    for cue, (s0, s1), level in spans:
        delta = level - typical
        if cue.labels:
            continue
        if delta >= cfg["raised_db"] and not (cfg["exclamation_counts_as_raised"] and "!" in cue.text):
            kind = "louder"
        elif delta <= cfg["quiet_db"]:
            kind = "quieter"
        else:
            continue
        measured = {"line_dbfs": round(float(level), 1), "typical_line_dbfs": round(typical, 1),
                    "delta_db": round(float(delta), 1)}
        caveat = ""
        if ctx.me is not None:
            me_level = ctx.me.level_dbfs(s0, s1)
            measured["me_dbfs"] = round(float(me_level), 1)
            if kind == "louder" and me_level >= level - 6:
                caveat = " Music and effects are nearly as loud here, so some of that may not be the voice."
        out.append(ctx.finding(
            "accuracy.unmarked_tone", REVIEW, s0, s1,
            f"This line is {abs(delta):.1f} dB {kind} than this program's typical line, and the caption marks "
            f"no manner of speaking: \"{cue.text}\". If it is shouted or whispered, a Deaf viewer can't tell. "
            f"A person decides whether it needs a label.{caveat}",
            cue=cue.index, measured=measured))
    return out
