"""Write one planted caption file per defect in clips/plants.json, next to the fetched clips.

    python scripts/plant_defects.py [--dest clips/cache]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from captioncheck import captions, plant  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(ROOT / "clips" / "cache"))
    args = ap.parse_args()
    dest = Path(args.dest)
    manifest = json.loads((ROOT / "clips" / "manifest.json").read_text())
    plants = json.loads((ROOT / "clips" / "plants.json").read_text())
    reference = captions.load(dest / manifest["subtitles"]["file"])
    (dest / "planted").mkdir(exist_ok=True)
    for seg, items in plants["segments"].items():
        for item in items:
            out = dest / "planted" / f"{seg}.{item['id']}.srt"
            out.write_text(captions.to_srt(plant.apply(reference.cues, item)))
            print(out.relative_to(dest))


if __name__ == "__main__":
    main()
