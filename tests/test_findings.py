import io
import json

import pytest

from captioncheck.findings import FAIL, Finding, FindingRejected, timecode, validate, write_jsonl

SPEECH = {"kind": "speech", "id": "faster-whisper:small.en", "version": "d1d751a5"}
GLYPHS = {"kind": "glyphs", "id": "glyphs:liberation-sans-regular", "version": "0123456789abcdef"}
H = "a" * 64


def make(**kw):
    base = dict(check="synchronicity.late_start", disposition=FAIL, start=1.0, end=1.7,
                message="late", audio_span_sha256=H, models=[SPEECH], cue=3)
    base.update(kw)
    return Finding(**base)


def test_complete_finding_is_accepted_and_versioned():
    f = make()
    validate(f)
    assert f.check_version == 1


@pytest.mark.parametrize("kw, why", [
    ({"audio_span_sha256": ""}, "audio-span"),
    ({"models": []}, "speech model"),
    ({"models": [GLYPHS]}, "speech model"),
    ({"check": "placement.line_width", "models": [SPEECH]}, "glyphs model"),
    ({"check": "made.up"}, "unknown check"),
    ({"disposition": "pass"}, "disposition"),
    ({"start": 2.0, "end": 1.0}, "timecode"),
    ({"check_version": 7}, "running version"),
    ({"models": [{"kind": "speech", "id": "x"}]}, "kind, an id and a version"),
])
def test_finding_without_its_evidence_is_rejected(kw, why):
    with pytest.raises(FindingRejected, match=why):
        validate(make(**kw))


def test_text_only_check_needs_no_model():
    validate(make(check="synchronicity.reading_rate", models=[]))


def test_one_bad_finding_writes_nothing():
    out = io.StringIO()
    with pytest.raises(FindingRejected):
        write_jsonl(out, [make(), make(audio_span_sha256="nope")], {"config_sha256": "c"})
    assert out.getvalue() == ""


def test_written_line_carries_timecode_hashes_check_and_models():
    out = io.StringIO()
    write_jsonl(out, [make()], {"audio_sha256": "b" * 64, "config_sha256": "c" * 64,
                                "run_models": [SPEECH, GLYPHS]}, fps=24)
    row = json.loads(out.getvalue())
    assert row["timecode"]["in"] == "00:00:01:00" and row["timecode"]["out"] == "00:00:01:17"
    assert row["evidence"]["audio_span_sha256"] == H and row["evidence"]["config_sha256"] == "c" * 64
    assert row["check"] == "synchronicity.late_start" and row["check_version"] == 1
    assert row["models"] == [SPEECH] and row["evidence"]["run_models"] == [SPEECH, GLYPHS]


def test_timecodes():
    assert timecode(3723.006) == "01:02:03.006"
    assert timecode(61.5, fps=25) == "00:01:01:13"
