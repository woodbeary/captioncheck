"""Align caption words to the words a speech model heard, in order, within a time window.

Exact matches say a caption word was heard. Short runs of different words in
the same place (a name spelled "Thom" heard as "Tom") still pin down when that
part of the caption was spoken, so they time a cue but don't count as heard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .captions import Cue, tokens
from .words import Word

SOFT_RUN = 4


@dataclass
class CueTiming:
    cue: Cue
    n_tokens: int
    heard: int = 0
    words: list[int] = field(default_factory=list)

    @property
    def heard_ratio(self) -> float:
        return self.heard / self.n_tokens if self.n_tokens else 0.0


@dataclass
class Alignment:
    cues: list[CueTiming]
    word_cue: list[int | None]
    heard_tokens: int
    caption_tokens: int

    @property
    def ratio(self) -> float:
        return self.heard_tokens / self.caption_tokens if self.caption_tokens else 0.0


def align(cues: list[Cue], words: list[Word], window: float) -> Alignment:
    cap_tok, cap_cue = [], []
    for ci, cue in enumerate(cues):
        for t in cue.tokens:
            cap_tok.append(t)
            cap_cue.append(ci)
    asr_tok, asr_word = [], []
    for wi, w in enumerate(words):
        for t in tokens(w.text):
            asr_tok.append(t)
            asr_word.append(wi)

    timings = [CueTiming(cue, len(cue.tokens)) for cue in cues]
    word_cue: list[int | None] = [None] * len(words)

    def pair(i: int, j: int, exact: bool) -> None:
        ci, wi = cap_cue[i], asr_word[j]
        cue = cues[ci]
        if not (cue.start - window <= words[wi].mid <= cue.end + window):
            return
        if exact:
            timings[ci].heard += 1
        if wi not in timings[ci].words:
            timings[ci].words.append(wi)
        word_cue[wi] = ci

    ops = SequenceMatcher(None, cap_tok, asr_tok, autojunk=False).get_opcodes()
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            for k in range(i2 - i1):
                pair(i1 + k, j1 + k, exact=True)
        elif tag == "replace" and i2 - i1 <= SOFT_RUN and j2 - j1 <= SOFT_RUN:
            for k in range(i2 - i1):
                pair(i1 + k, j1 + (k * (j2 - j1)) // (i2 - i1), exact=False)

    heard = sum(t.heard for t in timings)
    return Alignment(timings, word_cue, heard, len(cap_tok))


def speech_span(timing: CueTiming, words: list[Word], word_cap: float) -> tuple[float, float] | None:
    if not timing.words:
        return None
    return (min(words[i].start for i in timing.words),
            max(words[i].end_within(word_cap) for i in timing.words))
