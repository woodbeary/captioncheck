# Grading plan: thresholds set by Deaf viewers

**Status, 2026-11-01: no grades have been collected.** Every default in
captioncheck comes from a public style guide or from engineering judgment, and
`captioncheck/config.py` says which, key by key. This document is how that
changes, and what the code already does to make the change mechanical.

## Why grades, and why more than one kind of reader

- **The person who checks captions is usually hearing.** They heard the line
  that has no caption, so they don't miss it. The person who would miss it
  is the one who should set the threshold.
- **One pace is wrong for half the readers.** My stepdad was born Deaf and
  reads captions fast. Someone who lost their hearing later in life may need
  slower, larger captions. A threshold averaged across both fails both. So
  grades are kept per reader group, and the strictest group sets the default.

## Who grades

- Deaf and hard-of-hearing adults who read captions every day, paid for their
  time. The first person I'll ask is my stepdad, and his grades are used only
  with his OK.
- Each reviewer names their own reader group in their own words (for example
  "fast" or "steady"). No medical details, no audiograms.
- Instructions and the one question are offered in ASL as well as English.

## What they watch

The same public clips the tests use (*Tears of Steel*, CC BY 3.0), sound off
and captions on, played in an ordinary player at a display profile under test
(`tv-1080p`, then `phone-large`); captioncheck itself renders no video. Each
clip carries one planted defect at a controlled size, mixed with unmodified
controls. `captioncheck.plant` can already make the late starts (`shift`).
Ending a cue early by a set amount and retiming a cue to a set reading rate
are two more operations to add before grading starts:

| Check | Sizes graded |
| --- | --- |
| `synchronicity.late_start` | 0, 0.25, 0.5, 0.75, 1.0, 1.5 s late |
| `synchronicity.early_end` | 0, 0.25, 0.5, 1.0 s early |
| `synchronicity.reading_rate` | retimed to 14, 17, 20, 23, 26 characters per second |

Order is randomized, the reviewer doesn't know the size, and every size gets
at least five grades per reader group before it counts. Dropped lines and
unlabelled sounds come later, as "did you miss something here?" with the
answer shown afterwards.

## The grade

One question per clip, answered 1 to 4:

1. Fine.
2. I noticed, but it was fine.
3. I lost something.
4. I lost the line.

## From grades to thresholds

```
captioncheck calibrate grades.csv > thresholds.toml
captioncheck check captions.srt --audio program.wav --config thresholds.toml
```

Grades CSV columns: `reviewer, group, check, magnitude, grade`. For each reader
group and check, the threshold is the largest size at which at least 80% of
grades are 1 or 2, at that size and every smaller one. Sizes with fewer than
five grades never set a threshold. The strictest group wins, and the output
lists every group's value next to it.

The output records the SHA-256 of the grades file. The thresholds file then
changes the config hash that every finding carries, so any finding can be
traced to the grades behind it. `tests/test_calibrate.py` exercises all of
this on synthetic grades made up inside the test.

## What stays out of this repository

- Grades belong to the people who gave them. They are stored under
  pseudonymous codes, with no names and no video of reviewers, and published
  only with each reviewer's OK. Without it, only the resulting thresholds and
  the grade counts are published.
- No real grades are in this repository today.

## What grades can't settle

- **The speech model's own timing error is inside every sync threshold.**
  Grades calibrate the whole measurement: caption timing as read against
  Whisper `small.en` at one revision. A different model or revision needs a
  check against a graded set before its thresholds are trusted.
- **Tone is more than loudness.** captioncheck can flag a line that is much
  louder or quieter than usual with nothing marking it. It can't hear sarcasm.
  Whether a line needs a manner label stays a person's call.
