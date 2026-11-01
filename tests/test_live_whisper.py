"""Optional: run the speech model live and compare it with the recorded fixtures.

    CAPTIONCHECK_LIVE_WHISPER=1 pytest -m whisper

Needs `pip install '.[whisper]'` and the fetched clips. The int8 CPU kernels
can differ slightly between processors, so this compares within tolerances
instead of byte for byte, then reruns every planted defect on live timings.
"""

from __future__ import annotations

import os
from difflib import SequenceMatcher
from statistics import median

import pytest

from captioncheck import captions, engine, plant
from captioncheck.captions import tokens

from test_golden import PLANTS, load, matching

pytestmark = [pytest.mark.whisper, pytest.mark.clips,
              pytest.mark.skipif(os.environ.get("CAPTIONCHECK_LIVE_WHISPER") != "1",
                                 reason="set CAPTIONCHECK_LIVE_WHISPER=1 to run the model")]


@pytest.mark.parametrize("seg_id", ["bridge", "set"])
def test_live_model_agrees_with_the_recording_and_still_catches_every_plant(seg_id):
    from captioncheck.transcribe import transcribe
    mix, me, reference, recorded = load(seg_id)
    live = transcribe(mix, model="small.en", offline=os.environ.get("HF_HUB_OFFLINE") == "1")
    assert live.audio_sha256 == recorded.audio_sha256

    a = [(t, w.start) for w in recorded.words for t in tokens(w.text)]
    b = [(t, w.start) for w in live.words for t in tokens(w.text)]
    sm = SequenceMatcher(None, [t for t, _ in a], [t for t, _ in b], autojunk=False)
    assert sm.ratio() >= 0.9
    shifts = [abs(a[i + k][1] - b[j + k][1]) for i, j, n in sm.get_matching_blocks() for k in range(n)]
    assert median(shifts) <= 0.1

    before = engine.run(reference, mix, live, me=me)
    for item in PLANTS["segments"][seg_id]:
        after = engine.run(captions.parse(captions.to_srt(plant.apply(reference.cues, item))), mix, live, me=me)
        for want in item.get("expect", []):
            assert matching(after, want) and not matching(before, want), (item["id"], want)
