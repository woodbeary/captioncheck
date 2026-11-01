"""Record the speech model's word timings for each fetched clip, for tests that run without the model.

    python scripts/record_fixtures.py [--model small.en] [--offline]

Run after fetch_clips.py. The fixtures carry the analysis-audio SHA-256, the
model repository revision and the decoding settings; tests refuse a fixture
whose audio hash doesn't match the clip.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from captioncheck import audio, words  # noqa: E402
from captioncheck.transcribe import transcribe  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", default=str(ROOT / "clips" / "cache"))
    ap.add_argument("--out", default=str(ROOT / "tests" / "fixtures" / "words"))
    ap.add_argument("--model", default="small.en")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    manifest = json.loads((ROOT / "clips" / "manifest.json").read_text())
    Path(args.out).mkdir(parents=True, exist_ok=True)
    for seg in manifest["segments"]:
        clip = audio.load(Path(args.clips) / f"{seg['id']}.mix.wav")
        if clip.sha256 != seg["sha256"]["mix_wav"]:
            raise SystemExit(f"{seg['id']}: clip hash doesn't match the manifest; run fetch_clips.py")
        t = transcribe(clip, model=args.model, offline=args.offline)
        out = Path(args.out) / f"{seg['id']}.{args.model}.json"
        words.save(out, t)
        print(f"{out.name}: {len(t.words)} words, {t.model_ref['id']}@{t.model_ref['version'][:12]}")


if __name__ == "__main__":
    main()
