"""Read SubRip (.srt) and WebVTT (.vtt) caption files into cues.

A cue keeps its lines exactly as authored, because line breaks are part of
what a viewer reads. Sound and tone labels ("[gunfire]", "(whispering)",
music notes) are separated from spoken words, so sync and completeness
compare only what was said, while the sound check can see which cues carry
non-speech information.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

_TIME = r"(?:(\d+):)?(\d{1,2}):(\d{2})[,.](\d{3})"
_TIMING = re.compile(rf"^\s*{_TIME}\s*-->\s*{_TIME}")
_MARKUP = re.compile(r"<[^>]+>|\{\\[^}]*\}")
_LABEL = re.compile(r"\[[^\]]*\]|\([^)]*\)")
_MUSIC = "♪♫"
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")


def _seconds(h: str | None, m: str, s: str, ms: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


@dataclass(frozen=True)
class Cue:
    index: int
    start: float
    end: float
    lines: tuple[str, ...]

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def text(self) -> str:
        """What the viewer reads, markup removed, line breaks as spaces."""
        return " ".join(_MARKUP.sub("", line).strip() for line in self.lines).strip()

    @property
    def chars(self) -> int:
        """Characters a viewer reads, markup removed; line breaks not counted."""
        return sum(len(_MARKUP.sub("", line).strip()) for line in self.lines)

    @property
    def display_lines(self) -> list[str]:
        return [_MARKUP.sub("", line).strip() for line in self.lines]

    @property
    def labels(self) -> list[str]:
        """Sound, music and manner labels, e.g. '[gunfire]', '(whispers)', '♪'."""
        found = _LABEL.findall(self.text)
        if any(ch in self.text for ch in _MUSIC):
            found.append("♪")
        return found

    @property
    def spoken(self) -> str:
        """The words a speaker says, with labels and music notes removed."""
        text = _LABEL.sub(" ", self.text)
        for ch in _MUSIC:
            text = text.replace(ch, " ")
        return re.sub(r"\s+", " ", text).strip()

    @property
    def tokens(self) -> list[str]:
        return tokens(self.spoken)


def tokens(text: str) -> list[str]:
    """Lowercase word tokens with curly apostrophes folded, for alignment."""
    folded = text.lower().replace("’", "'").replace("‘", "'")
    return [t.replace("'", "") for t in _WORD.findall(folded)]


@dataclass
class Captions:
    cues: list[Cue]
    sha256: str
    source: str = ""
    warnings: list[str] = field(default_factory=list)


def parse(text: str, source: str = "", sha256: str | None = None) -> Captions:
    """Parse SRT or WebVTT text. Cue numbers are re-indexed from 1 in file order.

    sha256 defaults to the hash of the text as UTF-8; load() passes the file's own.
    """
    raw = text.encode("utf-8")
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[Cue] = []
    warnings: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line for line in block.split("\n") if line.strip() != ""]
        timing_at = next((i for i, line in enumerate(lines) if _TIMING.match(line)), None)
        if timing_at is None:
            continue
        g = _TIMING.match(lines[timing_at]).groups()
        start, end = _seconds(*g[0:4]), _seconds(*g[4:8])
        body = tuple(line.rstrip() for line in lines[timing_at + 1 :])
        if end <= start:
            warnings.append(f"cue {len(cues) + 1}: end {end:.3f} is not after start {start:.3f}")
        cues.append(Cue(index=len(cues) + 1, start=start, end=end, lines=body))
    return Captions(cues=cues, sha256=sha256 or hashlib.sha256(raw).hexdigest(), source=source,
                    warnings=warnings)


def load(path: str | Path) -> Captions:
    """Read a caption file. Its sha256 is the hash of the file's bytes, byte-order mark and all,
    so `sha256sum` on the file gives the hash a finding carries."""
    p = Path(path)
    raw = p.read_bytes()
    return parse(raw.decode("utf-8-sig"), source=p.name, sha256=hashlib.sha256(raw).hexdigest())


def _stamp(t: float, sep: str) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(cues: list[Cue]) -> str:
    blocks = []
    for n, cue in enumerate(cues, start=1):
        body = "\n".join(cue.lines)
        blocks.append(f"{n}\n{_stamp(cue.start, ',')} --> {_stamp(cue.end, ',')}\n{body}\n")
    return "\n".join(blocks)
