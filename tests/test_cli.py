import json

from captioncheck import audio, cli, words

from conftest import CLEAN_SRT, make_program


def _files(tmp_path, srt_text, prog=None):
    prog = prog or make_program()
    (tmp_path / "c.srt").write_text(srt_text)
    audio.write_wav(tmp_path / "a.wav", prog.audio)
    words.save(tmp_path / "w.json", prog.transcript)
    return ["--audio", str(tmp_path / "a.wav"), "--words", str(tmp_path / "w.json")]


def test_clean_file_exits_0(tmp_path, capsys):
    args = _files(tmp_path, CLEAN_SRT)
    assert cli.main(["check", str(tmp_path / "c.srt"), *args]) == 0
    assert "PASS" in capsys.readouterr().out


def test_fail_exits_1_and_writes_evidence(tmp_path, capsys):
    late = CLEAN_SRT.replace("00:00:04,000 --> 00:00:05,600", "00:00:04,900 --> 00:00:06,000")
    args = _files(tmp_path, late)
    out = tmp_path / "f.jsonl"
    assert cli.main(["check", str(tmp_path / "c.srt"), *args, "--jsonl", str(out), "--fps", "24"]) == 1
    [row] = [json.loads(x) for x in out.read_text().splitlines()]
    assert row["check"] == "synchronicity.late_start" and row["timecode"]["in"] == "00:00:04:00"
    ev = row["evidence"]
    assert len(ev["audio_span_sha256"]) == 64 and len(ev["audio_sha256"]) == 64 and len(ev["config_sha256"]) == 64
    assert row["models"][0]["id"] == "synthetic:fixture"
    assert "FAIL" in capsys.readouterr().out


def test_review_only_exits_2(tmp_path):
    no_label = CLEAN_SRT.replace("4\n00:00:09,900 --> 00:00:11,000\n[door slams]\n\n", "")
    args = _files(tmp_path, no_label)
    assert cli.main(["check", str(tmp_path / "c.srt"), *args]) == 2


def test_transcript_of_other_audio_exits_3(tmp_path, capsys):
    args = _files(tmp_path, CLEAN_SRT)
    other = make_program(phrases=[("other words", 1.0, 2.0, -20.0)])
    words.save(tmp_path / "w.json", other.transcript)
    assert cli.main(["check", str(tmp_path / "c.srt"), *args]) == 3
    assert "refused" in capsys.readouterr().err


def test_program_start_offsets_the_audio(tmp_path):
    from captioncheck import captions, plant
    shifted = captions.to_srt(plant.apply(captions.parse(CLEAN_SRT).cues, {"op": "shift", "cues": [1, 6], "by": 3600.0}))
    args = _files(tmp_path, shifted)
    assert cli.main(["check", str(tmp_path / "c.srt"), *args, "--start", "3600"]) == 0


def test_displays_lists_profiles(capsys):
    assert cli.main(["displays"]) == 0
    out = capsys.readouterr().out
    assert "tv-1080p" in out and "phone-large" in out and "hud-488" in out
