"""Fetch the demo clips: exact byte ranges of two uncompressed AIFF stems, plus the official subtitles.

    python scripts/fetch_clips.py            # fetch, verify every SHA-256, write clips/cache/
    python scripts/fetch_clips.py --pin      # first run only: print the hashes to pin

AIFF holds raw PCM, so a time range is a byte range: no decoder touches the
download, and captioncheck's integer downmix makes the analysis WAVs
bit-identical everywhere. A hash that doesn't match stops the run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from captioncheck import audio  # noqa: E402


def byte_range(aiff: dict, start: float, end: float) -> tuple[int, int]:
    frame = aiff["channels"] * aiff["bits"] // 8
    first = aiff["pcm_offset"] + int(round(start * aiff["rate"])) * frame
    last = aiff["pcm_offset"] + int(round(end * aiff["rate"])) * frame - 1
    return first, last


def get(url: str, rng: tuple[int, int] | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "captioncheck-fetch/0.1"})
    if rng:
        req.add_header("Range", f"bytes={rng[0]}-{rng[1]}")
    with urllib.request.urlopen(req, timeout=120) as r:
        if rng and r.status != 206:
            raise SystemExit(f"{url}: server answered {r.status}, not 206, to a Range request")
        body = r.read()
    if rng and len(body) != rng[1] - rng[0] + 1:
        raise SystemExit(f"{url}: got {len(body)} bytes, wanted {rng[1] - rng[0] + 1}")
    return body


def check(label: str, digest: str, pinned: str, pin: bool, pins: dict) -> None:
    if pin:
        pins[label] = digest
    elif digest != pinned:
        raise SystemExit(f"{label}: sha256 {digest} does not match the pinned {pinned}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(ROOT / "clips" / "cache"))
    ap.add_argument("--pin", action="store_true", help="print hashes instead of verifying them")
    args = ap.parse_args()
    manifest = json.loads((ROOT / "clips" / "manifest.json").read_text())
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    pins: dict[str, str] = {}

    subs = manifest["subtitles"]
    body = get(subs["url"])
    check("subtitles", hashlib.sha256(body).hexdigest(), subs["sha256"], args.pin, pins)
    (dest / subs["file"]).write_bytes(body)

    for seg in manifest["segments"]:
        for stem, info in manifest["stems"].items():
            rng = byte_range(manifest["aiff"], seg["start"], seg["end"])
            raw = get(info["url"], rng)
            check(f"{seg['id']}.{stem}_raw", hashlib.sha256(raw).hexdigest(),
                  seg["sha256"][f"{stem}_raw"], args.pin, pins)
            clip = audio.from_pcm24_stereo_48k(raw, offset=seg["start"])
            check(f"{seg['id']}.{stem}_wav", clip.sha256, seg["sha256"][f"{stem}_wav"], args.pin, pins)
            audio.write_wav(dest / f"{seg['id']}.{stem}.wav", clip)
            print(f"{seg['id']}.{stem}: {len(raw):,} bytes {rng[0]}-{rng[1]} -> {clip.seconds:.1f} s")

    if args.pin:
        print(json.dumps(pins, indent=2))
    else:
        print(f"all hashes match; clips in {dest}")


if __name__ == "__main__":
    main()
