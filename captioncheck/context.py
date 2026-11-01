from __future__ import annotations

from dataclasses import dataclass

from .align import Alignment
from .audio import Audio
from .captions import Cue
from .config import Config
from .findings import Finding
from .words import Word


@dataclass
class Context:
    """Everything a check may read. Times are program seconds throughout."""

    cues: list[Cue]
    words: list[Word]
    alignment: Alignment
    audio: Audio
    config: Config
    speech: dict
    me: Audio | None = None

    def finding(self, check: str, disposition: str, start: float, end: float, message: str,
                cue: int | None = None, measured: dict | None = None,
                models: list[dict] | None = None) -> Finding:
        return Finding(check=check, disposition=disposition, start=start, end=end, message=message,
                       audio_span_sha256=self.audio.span_sha256(start, end),
                       models=[self.speech] if models is None else models,
                       cue=cue, measured=measured or {})
