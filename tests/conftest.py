"""Synthetic programs: speech-level noise where the words are, a bang, and word timings bound to that audio."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from captioncheck import audio as audio_mod
from captioncheck import captions
from captioncheck.words import Transcript, Word

RATE = audio_mod.RATE
FAKE_MODEL = {"backend": "synthetic", "name": "fixture", "revision": "test-1"}

SCENE = [
    ("we have to leave now", 1.0, 2.4, -20.0),
    ("the robot is coming", 4.0, 5.2, -20.0),
    ("hold the door", 7.0, 7.9, -20.0),
    ("is everyone here", 12.0, 12.9, -20.0),
    ("i think so", 14.0, 14.8, -20.0),
]
BANG = (10.0, 10.4, -6.0)

CLEAN_SRT = """1
00:00:01,000 --> 00:00:02,800
We have to leave now.

2
00:00:04,000 --> 00:00:05,600
The robot is coming.

3
00:00:07,000 --> 00:00:08,400
Hold the door!

4
00:00:09,900 --> 00:00:11,000
[door slams]

5
00:00:12,000 --> 00:00:13,300
Is everyone here?

6
00:00:14,000 --> 00:00:15,200
I think so.
"""


def _noise(n: int, level_db: float, seed: int) -> np.ndarray:
    x = np.sin(np.arange(n) * 0.37 + seed) * np.sin(np.arange(n) * 0.011 * (seed % 7 + 1))
    x = x / np.sqrt(np.mean(x * x))
    return x * (10 ** (level_db / 20))


@dataclass
class Program:
    audio: audio_mod.Audio
    me: audio_mod.Audio
    transcript: Transcript


def make_program(phrases=SCENE, bangs=(BANG,), seconds: float = 16.0, p: float = 0.95,
                 offset: float = 0.0) -> Program:
    n = int(seconds * RATE)
    mix = _noise(n, -60.0, 1)
    me = _noise(n, -60.0, 2)
    words: list[Word] = []
    for k, (text, start, end, level) in enumerate(phrases):
        parts = text.split()
        step = (end - start) / len(parts)
        for i, w in enumerate(parts):
            ws, we = start + i * step, start + (i + 1) * step
            a, b = int(ws * RATE), int(we * RATE)
            mix[a:b] += _noise(b - a, level, 10 + k * 13 + i)
            words.append(Word(w, ws, we, p))
    for start, end, level in bangs:
        a, b = int(start * RATE), int(end * RATE)
        burst = _noise(b - a, level, 99)
        mix[a:b] += burst
        me[a:b] += burst
    to16 = lambda x: np.clip(np.round(x * 32767), -32768, 32767).astype(np.int16)  # noqa: E731
    mix_a = audio_mod.Audio(to16(mix), RATE, "synthetic", offset)
    me_a = audio_mod.Audio(to16(me), RATE, "synthetic", offset)
    return Program(mix_a, me_a, Transcript(mix_a.sha256, words, dict(FAKE_MODEL), {}))


def srt(text: str) -> captions.Captions:
    return captions.parse(text, source="test.srt")


@pytest.fixture
def program() -> Program:
    return make_program()
