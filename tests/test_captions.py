from captioncheck import captions


def test_srt_with_bom_crlf_and_markup():
    text = "﻿1\r\n00:00:01,000 --> 00:00:02,500\r\n<i>You're</i> a jerk,\r\nThom.\r\n\r\n2\r\n00:00:03,000 --> 00:00:04,000\r\n[door slams]\r\n"
    caps = captions.parse(text)
    assert [(c.start, c.end) for c in caps.cues] == [(1.0, 2.5), (3.0, 4.0)]
    assert caps.cues[0].lines == ("<i>You're</i> a jerk,", "Thom.")
    assert caps.cues[0].text == "You're a jerk, Thom."
    assert caps.cues[0].chars == len("You're a jerk,") + len("Thom.")
    assert len(caps.sha256) == 64


def test_webvtt_header_settings_and_short_timestamps():
    text = "WEBVTT\n\nNOTE made by hand\n\nintro\n00:01.000 --> 00:02.250 line:85% align:center\nHello there\n\n01:00:00.000 --> 01:00:01.000\nLater\n"
    caps = captions.parse(text)
    assert [(c.start, c.end, c.text) for c in caps.cues] == [(1.0, 2.25, "Hello there"), (3600.0, 3601.0, "Later")]


def test_labels_are_kept_apart_from_spoken_words():
    cue = captions.parse("1\n00:00:01,000 --> 00:00:02,000\n(whispering) Don’t move. [door creaks]\n").cues[0]
    assert cue.labels == ["(whispering)", "[door creaks]"]
    assert cue.spoken == "Don’t move."
    assert cue.tokens == ["dont", "move"]
    music = captions.parse("1\n00:00:01,000 --> 00:00:02,000\n♪ la la ♪\n").cues[0]
    assert music.labels == ["♪"] and music.tokens == ["la", "la"]


def test_backwards_cue_is_reported_not_dropped():
    caps = captions.parse("1\n00:00:05,000 --> 00:00:04,000\noops\n")
    assert len(caps.cues) == 1 and caps.warnings


def test_srt_round_trip():
    src = "1\n00:00:01,000 --> 00:00:02,500\nLine one\nLine two\n\n2\n01:02:03,004 --> 01:02:04,000\nThree\n"
    caps = captions.parse(src)
    again = captions.parse(captions.to_srt(caps.cues))
    assert [(c.start, c.end, c.lines) for c in again.cues] == [(c.start, c.end, c.lines) for c in caps.cues]
