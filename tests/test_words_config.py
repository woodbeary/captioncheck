import pytest

from captioncheck import words
from captioncheck.config import DEFAULTS, Config, source_of


def test_transcript_refuses_other_audio(program):
    with pytest.raises(words.TranscriptMismatch):
        program.transcript.bind("0" * 64, 0.0)


def test_bind_moves_words_to_program_time(program):
    bound = program.transcript.bind(program.audio.sha256, 100.0)
    assert bound[0].start == pytest.approx(program.transcript.words[0].start + 100.0)


def test_transcript_file_round_trip(tmp_path, program):
    p = tmp_path / "w.json"
    words.save(p, program.transcript)
    back = words.load(p)
    rounded = [(w.text, round(w.start, 3), round(w.end, 3), round(w.p, 3)) for w in program.transcript.words]
    assert [(w.text, w.start, w.end, w.p) for w in back.words] == rounded
    assert back.audio_sha256 == program.audio.sha256 and back.model == program.transcript.model


def test_long_word_before_a_pause_is_held_to_the_cap():
    w = words.Word("it's...", 15.76, 17.38, 0.81)
    assert w.end_within(0.5) == pytest.approx(16.26)
    assert words.Word("hi", 1.0, 1.2, 1.0).end_within(0.5) == 1.2


def test_config_overrides_change_the_hash_and_reject_typos(tmp_path):
    base = Config()
    stricter = Config({"reading": {"max_cps": 17.0}})
    assert stricter["reading"]["max_cps"] == 17.0 and stricter.sha256 != base.sha256
    with pytest.raises(ValueError, match="unknown setting"):
        Config({"reading": {"max_cps_typo": 1}})
    with pytest.raises(ValueError, match="unknown display"):
        Config({"placement": {"displays": ["nope"]}})


def test_every_default_has_a_stated_source():
    assert "Netflix" in source_of("reading.max_cps")
    for section, values in DEFAULTS.items():
        for key in values:
            assert source_of(f"{section}.{key}")
