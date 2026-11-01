"""Thresholds. Every default says where it came from; none comes from a Deaf viewer's grades yet.

Override any value with a TOML file (see thresholds.example.toml). The SHA-256
of the effective settings is stored on every finding, so a finding can always
be traced to the thresholds that produced it.
"""

from __future__ import annotations

import copy
import hashlib
import json
import tomllib
from dataclasses import asdict
from pathlib import Path

from .layout import DISPLAYS, Display

TTSG = "Netflix English (USA) Timed Text Style Guide"
JUDGMENT = "engineering default, to be replaced by graded thresholds (docs/GRADING-PLAN.md)"

DEFAULTS: dict = {
    "sync": {
        "late_start_s": 0.5,
        "early_start_s": 1.0,
        "early_end_s": 0.5,
        "search_window_s": 4.0,
        "word_cap_s": 0.5,
        "heard_ratio": 0.5,
        "unmatched_min_words": 3,
        "drift_ms_per_min": 100.0,
        "drift_min_cues": 6,
        "low_confidence_p": 0.5,
    },
    "completeness": {
        "min_words": 2,
        "on_screen_tolerance_s": 0.25,
        "join_gap_s": 1.0,
        "min_level_dbfs": -45.0,
        "low_confidence_p": 0.6,
    },
    "reading": {"max_cps": 20.0},
    "placement": {"displays": ["tv-1080p", "phone-large"]},
    "sound": {
        "min_dbfs": -30.0,
        "rise_db": 10.0,
        "background_s": 3.0,
        "min_event_s": 0.1,
        "merge_gap_s": 1.0,
        "label_reach_s": 1.0,
        "speech_guard_s": 0.2,
    },
    "tone": {"raised_db": 8.0, "quiet_db": -12.0, "exclamation_counts_as_raised": True},
    "run": {"min_alignment": 0.3},
}

SOURCES: dict = {
    "reading.max_cps": f"{TTSG}: adult programs up to 20 characters per second (17 for children's programs)",
    "placement.displays": "display profiles in captioncheck/layout.py; their sizes are stated assumptions",
    "sync.word_cap_s": "about twice the median word length (0.22-0.26 s) in the recorded demo transcripts",
}


def source_of(key: str) -> str:
    return SOURCES.get(key, JUDGMENT)


def _merge(base: dict, override: dict, path: str = "") -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if k == "displays" and not path:
            continue
        if k not in out:
            raise ValueError(f"unknown setting {path}{k}")
        out[k] = _merge(out[k], v, f"{path}{k}.") if isinstance(v, dict) else v
    return out


class Config:
    def __init__(self, override: dict | None = None):
        override = override or {}
        self.values = _merge(DEFAULTS, override)
        self.displays = dict(DISPLAYS)
        for display_id, d in override.get("displays", {}).items():
            self.displays[display_id] = Display(id=display_id, **d)
        for display_id in self.values["placement"]["displays"]:
            if display_id not in self.displays:
                raise ValueError(f"unknown display {display_id}")
        canonical = json.dumps({"values": self.values,
                                "displays": {k: asdict(v) for k, v in sorted(self.displays.items())}},
                               sort_keys=True)
        self.sha256 = hashlib.sha256(canonical.encode()).hexdigest()

    def __getitem__(self, section: str) -> dict:
        return self.values[section]

    @classmethod
    def load(cls, path: str | Path | None) -> "Config":
        if path is None:
            return cls()
        with open(path, "rb") as f:
            return cls(tomllib.load(f))
