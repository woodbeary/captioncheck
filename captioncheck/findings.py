"""Findings, and the rule that a finding without its evidence is never written.

Every finding carries: the program timecode it covers, the SHA-256 of the
analysis-audio samples in that span, the check id and version, and the
versions of every model used in the run. A check that rests on a model (the
speech model for anything timed against speech, the glyph table for anything
measured in pixels) must also name that model on the finding itself, or the
finding is rejected when it is written.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

SPEECH, GLYPHS = "speech", "glyphs"

# check id -> (version, the kinds of model its findings rest on)
REGISTRY: dict[str, tuple[int, frozenset[str]]] = {
    "synchronicity.late_start": (1, frozenset({SPEECH})),
    "synchronicity.early_start": (1, frozenset({SPEECH})),
    "synchronicity.early_end": (1, frozenset({SPEECH})),
    "synchronicity.unmatched_cue": (1, frozenset({SPEECH})),
    "synchronicity.drift": (1, frozenset({SPEECH})),
    "synchronicity.reading_rate": (1, frozenset()),
    "completeness.uncaptioned_speech": (1, frozenset({SPEECH})),
    "placement.line_width": (1, frozenset({GLYPHS})),
    "placement.line_count": (1, frozenset({GLYPHS})),
    "accuracy.unlabelled_sound": (1, frozenset({SPEECH})),
    "accuracy.unmarked_tone": (1, frozenset({SPEECH})),
}
CHECKS: dict[str, int] = {k: v for k, (v, _) in REGISTRY.items()}

FAIL, REVIEW = "fail", "review"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class FindingRejected(ValueError):
    pass


@dataclass
class Finding:
    check: str
    disposition: str
    start: float
    end: float
    message: str
    audio_span_sha256: str
    models: list[dict]
    cue: int | None = None
    measured: dict = field(default_factory=dict)
    check_version: int = 0

    def __post_init__(self) -> None:
        if not self.check_version and self.check in CHECKS:
            self.check_version = CHECKS[self.check]


def validate(f: Finding) -> None:
    problems = []
    if f.check not in CHECKS:
        problems.append(f"unknown check {f.check!r}")
    elif f.check_version != CHECKS[f.check]:
        problems.append(f"check version {f.check_version} is not the running version {CHECKS[f.check]}")
    if f.disposition not in (FAIL, REVIEW):
        problems.append(f"disposition must be fail or review, not {f.disposition!r}")
    if not (f.start >= 0 and f.end >= f.start):
        problems.append(f"bad timecode {f.start}-{f.end}")
    if not _HEX64.match(f.audio_span_sha256 or ""):
        problems.append("no audio-span SHA-256")
    if any(not m.get("id") or not m.get("version") or not m.get("kind") for m in f.models):
        problems.append("every model named on a finding needs a kind, an id and a version")
    needed = REGISTRY[f.check][1] if f.check in REGISTRY else frozenset()
    missing = needed - {m.get("kind") for m in f.models}
    if missing:
        problems.append(f"rests on a {'/'.join(sorted(missing))} model but names none")
    if problems:
        raise FindingRejected(f"{f.check} at {timecode(f.start)}: " + "; ".join(problems))


def timecode(t: float, fps: float | None = None) -> str:
    """HH:MM:SS.mmm, or HH:MM:SS:FF when a frame rate is given (non-drop)."""
    if fps:
        frames = int(round(t * fps))
        nominal = int(round(fps))
        s, ff = divmod(frames, nominal)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        return f"{h:02d}:{m:02d}:{s:02d}:{ff:02d}"
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def record(f: Finding, context: dict, fps: float | None = None) -> dict:
    validate(f)
    return {
        "check": f.check,
        "check_version": f.check_version,
        "disposition": f.disposition,
        "timecode": {"in": timecode(f.start, fps), "out": timecode(f.end, fps),
                     "start_s": round(f.start, 3), "end_s": round(f.end, 3)},
        "cue": f.cue,
        "message": f.message,
        "measured": f.measured,
        "evidence": {"audio_span_sha256": f.audio_span_sha256, **context},
        "models": f.models,
    }


def write_jsonl(out: IO[str] | str | Path, findings: list[Finding], context: dict,
                fps: float | None = None) -> int:
    """Validate everything first, then write; one rejected finding writes nothing."""
    rows = [record(f, context, fps) for f in findings]
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    if isinstance(out, (str, Path)):
        Path(out).write_text(text)
    else:
        out.write(text)
    return len(rows)
