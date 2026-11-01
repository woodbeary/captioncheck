"""Word timings from a speech model, bound to the exact audio the model heard.

A transcript file records the SHA-256 of the analysis samples it was made from.
captioncheck refuses to check captions against a transcript of different audio:
that is how a model "analyzes" media it never received.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SCHEMA = "captioncheck.words/1"


class TranscriptMismatch(ValueError):
    pass


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    p: float

    @property
    def mid(self) -> float:
        return (self.start + self.end) / 2

    def end_within(self, cap: float) -> float:
        """End time, with the word held to at most cap seconds.

        Whisper often stretches a word that comes before a pause well into the
        silence after it; a span of speech shouldn't end in that silence.
        """
        return min(self.end, self.start + cap)


@dataclass
class Transcript:
    audio_sha256: str
    words: list[Word]
    model: dict
    params: dict

    @property
    def model_ref(self) -> dict:
        return {"kind": "speech", "id": f"{self.model.get('backend')}:{self.model.get('name')}",
                "version": str(self.model.get("revision") or self.model.get("version") or "")}

    def bind(self, audio_sha256: str, offset: float) -> list[Word]:
        """Word times in program seconds, after proving the transcript is of this audio."""
        if audio_sha256 != self.audio_sha256:
            raise TranscriptMismatch(
                f"transcript was made from audio {self.audio_sha256[:12]}..., "
                f"but the audio being checked is {audio_sha256[:12]}...")
        return [Word(w.text, w.start + offset, w.end + offset, w.p) for w in self.words]

    def to_json(self) -> dict:
        return {"schema": SCHEMA, "audio_sha256": self.audio_sha256, "model": self.model,
                "params": self.params,
                "words": [{"w": w.text, "s": round(w.start, 3), "e": round(w.end, 3), "p": round(w.p, 3)}
                          for w in self.words]}


def load(path: str | Path) -> Transcript:
    data = json.loads(Path(path).read_text())
    if data.get("schema") != SCHEMA:
        raise ValueError(f"{path}: not a {SCHEMA} file")
    words = [Word(w["w"], float(w["s"]), float(w["e"]), float(w.get("p", 1.0))) for w in data["words"]]
    return Transcript(data["audio_sha256"], words, data["model"], data.get("params", {}))


def save(path: str | Path, transcript: Transcript) -> None:
    """One word per line, so a re-recorded fixture diffs word by word."""
    data = transcript.to_json()
    head = {k: v for k, v in data.items() if k != "words"}
    lines = json.dumps(head, indent=1, ensure_ascii=False)[:-2]
    body = ",\n".join("  " + json.dumps(w, ensure_ascii=False) for w in data["words"])
    Path(path).write_text(f'{lines},\n "words": [\n{body}\n ]\n}}\n')
