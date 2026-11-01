"""captioncheck command line.

  captioncheck check CAPTIONS --audio AUDIO [--words WORDS.json] [--me STEM] [--start S] ...
  captioncheck transcribe AUDIO -o WORDS.json [--model small.en] [--offline]
  captioncheck displays

Exit status for check: 0 pass, 1 fail, 2 review only, 3 unverified or refused.
"""

from __future__ import annotations

import argparse
import sys

from . import audio as audio_mod
from . import captions, engine, findings, report, words
from .config import Config
from .layout import DISPLAYS

EXIT = {engine.PASS: 0, findings.FAIL: 1, findings.REVIEW: 2, engine.UNVERIFIED: 3}


def _check(args: argparse.Namespace) -> int:
    caps = captions.load(args.captions)
    audio = audio_mod.load(args.audio, offset=args.start)
    me = audio_mod.load(args.me, offset=args.start) if args.me else None
    if args.words:
        transcript = words.load(args.words)
    else:
        from .transcribe import transcribe
        transcript = transcribe(audio, model=args.model, offline=args.offline)
    config = Config.load(args.config)
    try:
        result = engine.run(caps, audio, transcript, config, me=me)
    except words.TranscriptMismatch as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3
    if args.jsonl:
        findings.write_jsonl(args.jsonl, result.findings, result.context, args.fps)
    sys.stdout.write(report.text(result, args.fps))
    return EXIT[result.status]


def _transcribe(args: argparse.Namespace) -> int:
    from .transcribe import transcribe
    transcript = transcribe(audio_mod.load(args.audio), model=args.model, offline=args.offline)
    words.save(args.out, transcript)
    print(f"{len(transcript.words)} words from {transcript.model_ref['id']}@{transcript.model_ref['version'][:12]} "
          f"-> {args.out}")
    return 0


def _displays(_: argparse.Namespace) -> int:
    for d in DISPLAYS.values():
        print(f"{d.id:12} {d.width_px} px x {d.usable_ratio:.0%} = {d.usable_px:.0f} px usable, "
              f"{d.font_px:g} px type, {d.max_lines} lines. {d.about}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="captioncheck", description="Caption QC that reads like a Deaf viewer.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="check a caption file against the program audio")
    c.add_argument("captions")
    c.add_argument("--audio", required=True, help="program audio (16 kHz mono WAV as is; else via ffmpeg)")
    c.add_argument("--start", type=float, default=0.0, help="program time in seconds of the audio's first sample")
    c.add_argument("--words", help="recorded word timings; omit to transcribe now")
    c.add_argument("--me", help="music-and-effects stem on the same timeline, for the sound check")
    c.add_argument("--config", help="TOML thresholds")
    c.add_argument("--jsonl", help="write findings as JSON lines")
    c.add_argument("--fps", type=float, help="show timecodes as HH:MM:SS:FF at this frame rate")
    c.add_argument("--model", default="small.en")
    c.add_argument("--offline", action="store_true", help="never touch the network for the model")
    c.set_defaults(func=_check)

    t = sub.add_parser("transcribe", help="record word timings from the audio")
    t.add_argument("audio")
    t.add_argument("-o", "--out", required=True)
    t.add_argument("--model", default="small.en")
    t.add_argument("--offline", action="store_true")
    t.set_defaults(func=_transcribe)

    d = sub.add_parser("displays", help="list display profiles")
    d.set_defaults(func=_displays)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
