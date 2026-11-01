"""Run every check on one caption file against one program's audio and word timings."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import __version__
from .align import align
from .audio import Audio
from .captions import Captions
from .checks import ALL
from .config import Config
from .context import Context
from .findings import FAIL, REVIEW, Finding, validate
from .layout import glyph_table
from .words import Transcript

PASS, UNVERIFIED = "pass", "unverified"


@dataclass
class Run:
    status: str
    findings: list[Finding]
    context: dict
    reasons: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def run(captions: Captions, audio: Audio, transcript: Transcript, config: Config | None = None,
        me: Audio | None = None) -> Run:
    config = config or Config()
    words = transcript.bind(audio.sha256, audio.offset)
    if me is not None and (me.offset != audio.offset or me.rate != audio.rate):
        raise ValueError("the music-and-effects stem must share the mix's rate and start time")
    lo, hi = audio.offset, audio.offset + audio.seconds
    cues = [c for c in captions.cues if c.end > lo and c.start < hi]
    alignment = align(cues, words, config["sync"]["search_window_s"])
    ctx = Context(cues, words, alignment, audio, config, transcript.model_ref, me)

    findings: list[Finding] = []
    for check in ALL:
        findings.extend(check(ctx))
    for f in findings:
        validate(f)
    findings.sort(key=lambda f: (f.start, f.check))

    tables = {glyph_table(config.displays[d].glyphs).model_ref["id"]: glyph_table(config.displays[d].glyphs)
              for d in config["placement"]["displays"]}
    context = {
        "captioncheck": __version__,
        "captions_sha256": captions.sha256,
        "audio_sha256": audio.sha256,
        "audio_decoder": audio.decoder,
        "audio_program_start_s": audio.offset,
        "me_sha256": me.sha256 if me is not None else None,
        "config_sha256": config.sha256,
        "run_models": [transcript.model_ref] + [t.model_ref for t in tables.values()],
    }
    stats = {
        "cues_checked": len(cues),
        "cues_outside_audio": len(captions.cues) - len(cues),
        "words_heard": len(words),
        "caption_words_heard": round(alignment.ratio, 3),
    }

    reasons = []
    if alignment.caption_tokens >= 10 and alignment.ratio < config["run"]["min_alignment"]:
        reasons.append(
            f"only {alignment.ratio:.0%} of caption words were heard in the audio (minimum "
            f"{config['run']['min_alignment']:.0%}): wrong audio, wrong program start, timings beyond "
            f"the {config['sync']['search_window_s']:g} s search window, or a model that didn't hear the media. "
            f"Speech-timed results can't be trusted, so this run can't pass.")
    if reasons:
        status = UNVERIFIED
    elif any(f.disposition == FAIL for f in findings):
        status = FAIL
    elif any(f.disposition == REVIEW for f in findings):
        status = REVIEW
    else:
        status = PASS
    return Run(status, findings, context, reasons, stats)
