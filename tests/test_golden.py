"""The real clip: official Tears of Steel subtitles, then one planted defect at a time.

Needs `python scripts/fetch_clips.py` first. Skipped without the clips, unless
CAPTIONCHECK_REQUIRE_CLIPS=1 (as in CI), which turns a missing clip into a failure.
The speech model's word timings come from the recorded fixtures.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from captioncheck import audio, captions, engine, plant, words
from captioncheck.findings import FAIL, REVIEW, write_jsonl

ROOT = Path(__file__).resolve().parent.parent
CLIPS = Path(os.environ.get("CAPTIONCHECK_CLIPS", ROOT / "clips" / "cache"))
FIXTURES = ROOT / "tests" / "fixtures" / "words"
MANIFEST = json.loads((ROOT / "clips" / "manifest.json").read_text())
PLANTS = json.loads((ROOT / "clips" / "plants.json").read_text())
SEGMENTS = {s["id"]: s for s in MANIFEST["segments"]}

pytestmark = pytest.mark.clips


def _need(path: Path) -> Path:
    if not path.exists():
        if os.environ.get("CAPTIONCHECK_REQUIRE_CLIPS") == "1":
            pytest.fail(f"{path} is missing; run scripts/fetch_clips.py")
        pytest.skip("clips not fetched (scripts/fetch_clips.py)")
    return path


def load(seg_id: str, transcript_path: Path | None = None):
    seg = SEGMENTS[seg_id]
    mix = audio.load(_need(CLIPS / f"{seg_id}.mix.wav"), offset=seg["start"])
    me = audio.load(_need(CLIPS / f"{seg_id}.me.wav"), offset=seg["start"])
    reference = captions.load(_need(CLIPS / MANIFEST["subtitles"]["file"]))
    transcript = words.load(transcript_path or FIXTURES / f"{seg_id}.small.en.json")
    return mix, me, reference, transcript


def overlaps(f, window):
    return f.start <= window[1] and f.end >= window[0]


def matching(run, want):
    return [f for f in run.findings if f.check == want["check"] and overlaps(f, want["within"])
            and ("display" not in want or f.measured.get("display") == want["display"])]


@pytest.mark.parametrize("seg_id", SEGMENTS)
def test_clips_and_fixtures_are_the_pinned_audio(seg_id):
    mix, me, reference, transcript = load(seg_id)
    pins = SEGMENTS[seg_id]["sha256"]
    assert mix.sha256 == pins["mix_wav"] == transcript.audio_sha256
    assert me.sha256 == pins["me_wav"]
    assert reference.sha256 == MANIFEST["subtitles"]["sha256"]
    assert transcript.model["revision"] == "d1d751a5f8271d482d14ca55d9e2deeebbae577f"


def test_what_the_readme_reports_on_the_official_subtitles():
    mix, me, reference, transcript = load("bridge")
    bridge = engine.run(reference, mix, transcript, me=me)
    [fast] = [f for f in bridge.findings if f.check == "synchronicity.reading_rate" and f.cue == 8]
    assert fast.measured["cps"] == 43.0
    assert not [f for f in bridge.findings if f.check.startswith("placement.")]

    mix, me, reference, transcript = load("set")
    s = engine.run(reference, mix, transcript, me=me)
    [late] = [f for f in s.findings if f.check == "synchronicity.late_start" and f.cue == 48]
    assert late.measured["offset_s"] == 1.16
    gaps = {f.measured["heard"]: f.disposition for f in s.findings if f.check == "completeness.uncaptioned_speech"}
    assert gaps == {"Two minutes.": FAIL, "Come on!": REVIEW}
    assert not [f for f in s.findings if f.check == "accuracy.unmarked_tone"]
    assert bridge.stats["caption_words_heard"] == 0.886 and s.stats["caption_words_heard"] == 0.811


PLANT_CASES = [(seg_id, p) for seg_id, items in PLANTS["segments"].items() for p in items]


@pytest.mark.parametrize("seg_id, item", PLANT_CASES, ids=[f"{s}-{p['id']}" for s, p in PLANT_CASES])
def test_each_planted_defect_is_caught(seg_id, item, tmp_path):
    mix, me, reference, transcript = load(seg_id)
    before = engine.run(reference, mix, transcript, me=me)
    planted = captions.parse(captions.to_srt(plant.apply(reference.cues, item)))
    after = engine.run(planted, mix, transcript, me=me)
    assert after.status != engine.UNVERIFIED
    for want in item.get("expect", []):
        assert matching(after, want), f"{item['id']}: no {want}"
        assert not matching(before, want), f"{item['id']}: {want} was already in the reference"
    for gone in item.get("clears", []):
        assert matching(before, gone) and not matching(after, gone)
    assert write_jsonl(tmp_path / "f.jsonl", after.findings, after.context) == len(after.findings)
