"""Every check on a synthetic program: a clean file passes, and each defect is caught for the right reason."""

import pytest

from captioncheck import captions, engine, plant, words
from captioncheck.config import Config
from captioncheck.findings import FAIL, REVIEW, validate

from conftest import CLEAN_SRT, SCENE, make_program, srt


def checks(run, kind=None):
    return [f for f in run.findings if kind is None or f.check == kind]


def test_clean_captions_pass_with_no_findings(program):
    run = engine.run(srt(CLEAN_SRT), program.audio, program.transcript)
    assert run.status == engine.PASS, [f.message for f in run.findings]
    assert run.findings == [] and run.stats["caption_words_heard"] == 1.0


def test_clean_captions_pass_with_the_effects_stem_too(program):
    run = engine.run(srt(CLEAN_SRT), program.audio, program.transcript, me=program.me)
    assert run.status == engine.PASS, [f.message for f in run.findings]


def test_late_caption(program):
    text = CLEAN_SRT.replace("00:00:04,000 --> 00:00:05,600", "00:00:04,900 --> 00:00:06,000")
    run = engine.run(srt(text), program.audio, program.transcript)
    [f] = checks(run, "synchronicity.late_start")
    assert f.disposition == FAIL and f.cue == 2
    assert f.measured["offset_s"] == pytest.approx(0.9, abs=0.01)
    assert (f.start, f.end) == (pytest.approx(4.0), pytest.approx(4.9))
    assert run.status == FAIL


def test_early_caption(program):
    text = CLEAN_SRT.replace("00:00:12,000 --> 00:00:13,300", "00:00:10,600 --> 00:00:13,300")
    run = engine.run(srt(text), program.audio, program.transcript)
    [f] = checks(run, "synchronicity.early_start")
    assert f.cue == 5 and f.measured["offset_s"] == pytest.approx(-1.4, abs=0.01)


def test_caption_leaves_before_the_line_ends(program):
    text = CLEAN_SRT.replace("00:00:01,000 --> 00:00:02,800", "00:00:01,000 --> 00:00:01,600")
    run = engine.run(srt(text), program.audio, program.transcript)
    [f] = checks(run, "synchronicity.early_end")
    assert f.cue == 1 and f.end == pytest.approx(2.4)


def test_missing_line_is_speech_with_no_caption(program):
    text = CLEAN_SRT.replace("2\n00:00:04,000 --> 00:00:05,600\nThe robot is coming.\n\n", "")
    run = engine.run(srt(text), program.audio, program.transcript)
    [f] = checks(run, "completeness.uncaptioned_speech")
    assert f.disposition == FAIL and f.measured["heard"] == "the robot is coming"
    assert (f.start, f.end) == (pytest.approx(4.0), pytest.approx(5.2))


def test_low_confidence_speech_goes_to_a_person():
    prog = make_program(p=0.3)
    text = CLEAN_SRT.replace("2\n00:00:04,000 --> 00:00:05,600\nThe robot is coming.\n\n", "")
    run = engine.run(srt(text), prog.audio, prog.transcript)
    [f] = checks(run, "completeness.uncaptioned_speech")
    assert f.disposition == REVIEW and "should listen" in f.message


def test_single_stray_word_is_not_a_missing_line():
    prog = make_program(phrases=[*SCENE, ("hey", 9.0, 9.3, -20.0)])
    run = engine.run(srt(CLEAN_SRT), prog.audio, prog.transcript)
    assert checks(run, "completeness.uncaptioned_speech") == []


def test_reading_rate(program):
    text = CLEAN_SRT.replace("00:00:12,000 --> 00:00:13,300\nIs everyone here?",
                             "00:00:12,000 --> 00:00:13,300\nIs everyone here? Did anybody see where Thom went?")
    run = engine.run(srt(text), program.audio, program.transcript)
    [f] = checks(run, "synchronicity.reading_rate")
    assert f.measured["cps"] > 20 and f.models == []
    relaxed = engine.run(srt(text), program.audio, program.transcript, Config({"reading": {"max_cps": 40}}))
    assert checks(relaxed, "synchronicity.reading_rate") == []


def test_line_width_is_measured_per_display(program):
    text = CLEAN_SRT.replace("We have to leave now.", "We have to leave now, or the robot will find us all.")
    text = text.replace("00:00:01,000 --> 00:00:02,800", "00:00:01,000 --> 00:00:03,800")
    run = engine.run(srt(text), program.audio, program.transcript)
    widths = checks(run, "placement.line_width")
    assert [f.measured["display"] for f in widths] == ["phone-large"]
    assert widths[0].models[0]["kind"] == "glyphs"
    assert widths[0].measured["line_px"][0] > widths[0].measured["usable_px"]


def test_too_many_lines(program):
    text = CLEAN_SRT.replace("We have to leave now.", "We have\nto leave\nnow.")
    run = engine.run(srt(text), program.audio, program.transcript)
    counts = checks(run, "placement.line_count")
    assert sorted(f.measured["display"] for f in counts) == ["phone-large", "tv-1080p"]
    assert all(f.measured["rendered_lines"] == 3 for f in counts)


def test_unlabelled_sound_is_flagged_for_a_person_never_labelled(program):
    text = CLEAN_SRT.replace("4\n00:00:09,900 --> 00:00:11,000\n[door slams]\n\n", "")
    for me in (None, program.me):
        run = engine.run(srt(text), program.audio, program.transcript, me=me)
        [f] = checks(run, "accuracy.unlabelled_sound")
        assert f.disposition == REVIEW and 9.9 < f.start < 10.1 and 10.3 < f.end < 10.5
        assert "captioncheck does not" in f.message
        assert ("me_span_sha256" in f.measured) == (me is not None)
        assert run.status == REVIEW


def test_shouted_line_with_no_mark_is_flagged():
    loud = [p if p[0] != "hold the door" else (p[0], p[1], p[2], -8.0) for p in SCENE]
    prog = make_program(phrases=loud)
    unmarked = CLEAN_SRT.replace("Hold the door!", "Hold the door.")
    [f] = checks(engine.run(srt(unmarked), prog.audio, prog.transcript), "accuracy.unmarked_tone")
    assert f.disposition == REVIEW and f.measured["delta_db"] == pytest.approx(12, abs=0.5)
    assert "louder" in f.message
    for marked in ("Hold the door!", "(shouting) Hold the door."):
        run = engine.run(srt(CLEAN_SRT.replace("Hold the door!", marked)), prog.audio, prog.transcript)
        assert checks(run, "accuracy.unmarked_tone") == []


def test_whispered_line_with_no_mark_is_flagged():
    quiet = [p if p[0] != "is everyone here" else (p[0], p[1], p[2], -34.0) for p in SCENE]
    prog = make_program(phrases=quiet)
    [f] = checks(engine.run(srt(CLEAN_SRT), prog.audio, prog.transcript), "accuracy.unmarked_tone")
    assert "quieter" in f.message and f.cue == 5


def _long_program():
    lines = ["move the cart", "watch the left side", "check the cable", "lights on now", "places everyone",
             "roll the camera", "quiet please", "and action"]
    phrases = [(t, 2.0 + 5 * i, 3.2 + 5 * i, -20.0) for i, t in enumerate(lines)]
    prog = make_program(phrases=phrases, bangs=(), seconds=42.0)
    return prog, phrases


def test_drift_from_a_frame_rate_mismatch():
    prog, phrases = _long_program()
    factor = 25 / 24
    body = "\n".join(
        f"{i + 1}\n00:00:{2 + (s - 2) * factor:06.3f} --> 00:00:{2 + (e + 0.4 - 2) * factor:06.3f}\n{t}\n".replace(".", ",")
        for i, (t, s, e, _) in enumerate(phrases))
    run = engine.run(srt(body), prog.audio, prog.transcript)
    [f] = checks(run, "synchronicity.drift")
    assert f.measured["ratio"] == pytest.approx(factor, abs=0.005)


def test_steady_offset_is_not_drift():
    prog, phrases = _long_program()
    body = "\n".join(f"{i + 1}\n00:00:{s + 0.3:06.3f} --> 00:00:{e + 0.5:06.3f}\n{t}\n".replace(".", ",")
                     for i, (t, s, e, _) in enumerate(phrases))
    assert checks(engine.run(srt(body), prog.audio, prog.transcript), "synchronicity.drift") == []


def test_captions_for_other_audio_are_unverified_never_pass(program):
    other = srt("1\n00:00:01,000 --> 00:00:03,000\nLorem ipsum dolor sit amet\n\n"
                "2\n00:00:04,000 --> 00:00:06,000\nconsectetur adipiscing elit sed do eiusmod\n")
    run = engine.run(other, program.audio, program.transcript)
    assert run.status == engine.UNVERIFIED and "0%" in run.reasons[0]


def test_transcript_of_other_audio_is_refused(program):
    other = make_program(phrases=[("something else entirely", 1.0, 2.0, -20.0)])
    with pytest.raises(words.TranscriptMismatch):
        engine.run(srt(CLEAN_SRT), program.audio, other.transcript)


def test_every_finding_carries_the_hash_of_its_own_span(program):
    text = (CLEAN_SRT.replace("00:00:04,000 --> 00:00:05,600", "00:00:04,900 --> 00:00:06,000")
            .replace("4\n00:00:09,900 --> 00:00:11,000\n[door slams]\n\n", ""))
    run = engine.run(srt(text), program.audio, program.transcript)
    assert len(run.findings) >= 2
    for f in run.findings:
        validate(f)
        assert f.audio_span_sha256 == program.audio.span_sha256(f.start, f.end)
    assert run.context["audio_sha256"] == program.audio.sha256
    assert {m["kind"] for m in run.context["run_models"]} == {"speech", "glyphs"}


def test_audio_that_starts_mid_program():
    prog = make_program(offset=100.0)
    caps = srt(captions.to_srt(plant.apply(srt(CLEAN_SRT).cues, {"op": "shift", "cues": [1, 6], "by": 100.0})))
    assert caps.cues[0].start == 101.0
    run = engine.run(caps, prog.audio, prog.transcript)
    assert run.status == engine.PASS and run.stats["cues_checked"] == 6


def test_cues_outside_the_audio_are_counted_not_checked(program):
    caps = srt(CLEAN_SRT + "\n7\n00:05:00,000 --> 00:05:02,000\nLong after the clip ends.\n")
    run = engine.run(caps, program.audio, program.transcript)
    assert run.status == engine.PASS
    assert run.stats["cues_checked"] == 6 and run.stats["cues_outside_audio"] == 1
