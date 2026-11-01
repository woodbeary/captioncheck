"""A plain-text report a person can read top to bottom."""

from __future__ import annotations

from collections import Counter

from .engine import Run
from .findings import timecode


def text(run: Run, fps: float | None = None) -> str:
    out = [f"captioncheck {run.context['captioncheck']}: {run.status.upper()}"]
    for reason in run.reasons:
        out.append(f"  unverified: {reason}")
    s = run.stats
    out.append(f"  {s['cues_checked']} cues checked ({s['cues_outside_audio']} outside the audio), "
               f"{s['words_heard']} words heard, {s['caption_words_heard']:.0%} of caption words heard")
    counts = Counter((f.disposition, f.check) for f in run.findings)
    for (disposition, check), n in sorted(counts.items()):
        out.append(f"  {disposition:6} {n:3}  {check}")
    out.append("")
    for f in run.findings:
        cue = f"cue {f.cue}" if f.cue is not None else ""
        out.append(f"{f.disposition.upper():6} {timecode(f.start, fps)}-{timecode(f.end, fps)} "
                   f"{f.check} v{f.check_version} {cue}")
        out.append(f"       {f.message}")
        out.append(f"       audio span {f.audio_span_sha256[:16]}  models "
                   + (", ".join(f"{m['id']}@{m['version'][:12]}" for m in f.models) or "none"))
    out.append("")
    out.append(f"audio {run.context['audio_sha256'][:16]} ({run.context['audio_decoder']}), "
               f"captions {run.context['captions_sha256'][:16]}, config {run.context['config_sha256'][:16]}")
    return "\n".join(out) + "\n"
