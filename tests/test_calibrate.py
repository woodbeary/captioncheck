"""Calibration on SYNTHETIC grades made up inside this test. No real reviewer's grades exist in this repo."""

import tomllib

from captioncheck import cli
from captioncheck.calibrate import group_thresholds, load_grades, thresholds


def _write(tmp_path, rows):
    lines = ["reviewer,group,check,magnitude,grade"]
    for reviewer, group, check, magnitude, grades in rows:
        lines += [f"{reviewer}{i},{group},{check},{magnitude},{g}" for i, g in enumerate(grades)]
    path = tmp_path / "synthetic-grades.csv"
    path.write_text("\n".join(lines) + "\n")
    return path


ROWS = [
    ("f", "fast", "synchronicity.late_start", 0.25, [1, 1, 1, 1, 1]),
    ("f", "fast", "synchronicity.late_start", 0.5, [1, 1, 2, 1, 2]),
    ("f", "fast", "synchronicity.late_start", 0.75, [1, 2, 2, 2, 3]),
    ("f", "fast", "synchronicity.late_start", 1.0, [3, 3, 4, 2, 3]),
    ("s", "steady", "synchronicity.late_start", 0.25, [1, 1, 1, 2, 1]),
    ("s", "steady", "synchronicity.late_start", 0.5, [2, 2, 1, 2, 2]),
    ("s", "steady", "synchronicity.late_start", 0.75, [3, 3, 2, 3, 4]),
    ("f", "fast", "synchronicity.reading_rate", 20, [1, 1, 1, 1, 2]),
    ("f", "fast", "synchronicity.reading_rate", 23, [1, 2, 2, 2, 1]),
    ("f", "fast", "synchronicity.reading_rate", 26, [3, 4, 3, 3, 2]),
    ("s", "steady", "synchronicity.reading_rate", 14, [1, 1, 1, 1, 1]),
    ("s", "steady", "synchronicity.reading_rate", 17, [2, 1, 2, 2, 1]),
    ("s", "steady", "synchronicity.reading_rate", 20, [3, 3, 2, 4, 3]),
]


def test_each_group_gets_its_own_threshold(tmp_path):
    rows, _ = load_grades(_write(tmp_path, ROWS))
    got = group_thresholds(rows)
    assert got[("fast", "synchronicity.late_start")] == 0.75
    assert got[("steady", "synchronicity.late_start")] == 0.5
    assert got[("fast", "synchronicity.reading_rate")] == 23
    assert got[("steady", "synchronicity.reading_rate")] == 17


def test_the_strictest_group_sets_the_default_and_the_grades_are_hashed(tmp_path):
    loaded = load_grades(_write(tmp_path, ROWS))
    text = thresholds(loaded)
    values = tomllib.loads(text)
    assert values["sync"]["late_start_s"] == 0.5
    assert values["reading"]["max_cps"] == 17
    assert loaded[1] in text and "fast: 23.0, steady: 17.0" in text


def test_too_few_grades_never_set_a_threshold(tmp_path):
    rows, _ = load_grades(_write(tmp_path, [("a", "fast", "synchronicity.late_start", 0.25, [1, 1, 1])]))
    assert group_thresholds(rows)[("fast", "synchronicity.late_start")] is None


def test_cli_prints_a_thresholds_file(tmp_path, capsys):
    assert cli.main(["calibrate", str(_write(tmp_path, ROWS))]) == 0
    assert tomllib.loads(capsys.readouterr().out)["reading"]["max_cps"] == 17
