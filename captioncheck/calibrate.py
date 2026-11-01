"""Turn Deaf reviewers' grades into thresholds. See docs/GRADING-PLAN.md.

No grades have been collected. This is the code that will read them, tested on
synthetic grades only.

Grades CSV columns: reviewer, group, check, magnitude, grade
  grade 1 = fine, 2 = noticed but fine, 3 = lost something, 4 = lost the line.
For each reader group and check, the threshold is the largest magnitude at
which, at that magnitude and every smaller one, at least ACCEPT of grades are
1 or 2. The strictest group sets the default, so the reader who needs the most
time isn't averaged away.
"""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from pathlib import Path

ACCEPT = 0.8
MIN_GRADES = 5
SETTINGS = {
    "synchronicity.late_start": ("sync", "late_start_s"),
    "synchronicity.early_end": ("sync", "early_end_s"),
    "synchronicity.reading_rate": ("reading", "max_cps"),
}


def load_grades(path: str | Path) -> tuple[list[dict], str]:
    raw = Path(path).read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    for r in rows:
        r["magnitude"] = float(r["magnitude"])
        r["grade"] = int(r["grade"])
        if r["grade"] not in (1, 2, 3, 4):
            raise ValueError(f"grade must be 1-4: {r}")
    return rows, hashlib.sha256(raw).hexdigest()


def group_thresholds(rows: list[dict]) -> dict[tuple[str, str], float | None]:
    by: dict[tuple[str, str], dict[float, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[(r["group"], r["check"])][r["magnitude"]].append(r["grade"])
    out: dict[tuple[str, str], float | None] = {}
    for key, mags in by.items():
        best = None
        for m in sorted(mags):
            grades = mags[m]
            if len(grades) < MIN_GRADES:
                break
            if sum(g <= 2 for g in grades) / len(grades) < ACCEPT:
                break
            best = m
        out[key] = best
    return out


def thresholds(loaded: tuple[list[dict], str]) -> str:
    rows, digest = loaded
    per_group = group_thresholds(rows)
    groups = sorted({g for g, _ in per_group})
    lines = [f"# from grades sha256 {digest}, {len(rows)} grades, reader groups: {', '.join(groups)}",
             f"# rule: largest magnitude with >= {ACCEPT:.0%} of grades 1-2 at it and below; strictest group wins"]
    by_section: dict[str, list[str]] = defaultdict(list)
    for check, (section, key) in SETTINGS.items():
        values = {g: per_group.get((g, check)) for g in groups if (g, check) in per_group}
        if not values:
            continue
        note = ", ".join(f"{g}: {v if v is not None else 'none acceptable'}" for g, v in values.items())
        if any(v is None for v in values.values()):
            by_section[section].append(f"# {key}: no acceptable magnitude for some group ({note}); keep the default")
            continue
        by_section[section].append(f"{key} = {min(values.values())}  # {note}")
    for section, entries in by_section.items():
        lines += ["", f"[{section}]", *entries]
    return "\n".join(lines) + "\n"
