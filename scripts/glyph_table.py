"""Measure per-glyph advance widths from a TrueType font into a captioncheck glyph table.

    python scripts/glyph_table.py /usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf \
        liberation-sans-regular > captioncheck/data/glyphs/liberation-sans-regular.json

Reads only the head, hhea, hmtx, cmap (format 4) and name tables, with the
standard library. Kerning is ignored, which usually overstates a line's width
slightly; for an overflow check that errs on the safe side.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys

CODEPOINTS = (list(range(0x20, 0x7F)) + list(range(0xA0, 0x100))
              + [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x266A, 0x266B])


def tables(data: bytes) -> dict[bytes, tuple[int, int]]:
    count = struct.unpack(">H", data[4:6])[0]
    out = {}
    for i in range(count):
        tag, _, offset, length = struct.unpack(">4sIII", data[12 + 16 * i : 28 + 16 * i])
        out[tag] = (offset, length)
    return out


def cmap_format4(data: bytes, cmap_at: int) -> dict[int, int]:
    n = struct.unpack(">H", data[cmap_at + 2 : cmap_at + 4])[0]
    for i in range(n):
        pid, eid, off = struct.unpack(">HHI", data[cmap_at + 4 + 8 * i : cmap_at + 12 + 8 * i])
        sub = cmap_at + off
        if (pid, eid) == (3, 1) and struct.unpack(">H", data[sub : sub + 2])[0] == 4:
            segs = struct.unpack(">H", data[sub + 6 : sub + 8])[0] // 2
            arr = lambda k: struct.unpack(f">{segs}H", data[sub + 14 + k : sub + 14 + k + 2 * segs])  # noqa: E731
            ends, starts = arr(0), arr(2 * segs + 2)
            deltas = struct.unpack(f">{segs}h", data[sub + 16 + 4 * segs : sub + 16 + 6 * segs])
            ro_at = sub + 16 + 6 * segs
            ranges = struct.unpack(f">{segs}H", data[ro_at : ro_at + 2 * segs])
            mapping = {}
            for s in range(segs):
                for cp in range(starts[s], ends[s] + 1):
                    if cp == 0xFFFF:
                        continue
                    if ranges[s] == 0:
                        gid = (cp + deltas[s]) & 0xFFFF
                    else:
                        at = ro_at + 2 * s + ranges[s] + 2 * (cp - starts[s])
                        gid = struct.unpack(">H", data[at : at + 2])[0]
                        gid = (gid + deltas[s]) & 0xFFFF if gid else 0
                    if gid:
                        mapping[cp] = gid
            return mapping
    raise SystemExit("no Windows Unicode BMP (3,1) format 4 cmap")


def name(data: bytes, at: int, name_id: int) -> str:
    count, string_at = struct.unpack(">HH", data[at + 2 : at + 6])
    for i in range(count):
        pid, eid, _, nid, length, off = struct.unpack(">6H", data[at + 6 + 12 * i : at + 18 + 12 * i])
        if pid == 3 and nid == name_id:
            s = at + string_at + off
            return data[s : s + length].decode("utf-16-be")
    return ""


def measure(path: str, table_id: str) -> dict:
    data = open(path, "rb").read()
    t = tables(data)
    units_per_em = struct.unpack(">H", data[t[b"head"][0] + 18 : t[b"head"][0] + 20])[0]
    n_metrics = struct.unpack(">H", data[t[b"hhea"][0] + 34 : t[b"hhea"][0] + 36])[0]
    hmtx = t[b"hmtx"][0]
    advances = [struct.unpack(">H", data[hmtx + 4 * i : hmtx + 4 * i + 2])[0] for i in range(n_metrics)]
    cmap = cmap_format4(data, t[b"cmap"][0])
    widths = {}
    for cp in CODEPOINTS:
        gid = cmap.get(cp)
        if gid is not None:
            widths[str(cp)] = advances[min(gid, n_metrics - 1)]
    return {
        "schema": "captioncheck.glyphs/1",
        "id": table_id,
        "font": {"family": name(data, t[b"name"][0], 4), "version": name(data, t[b"name"][0], 5),
                 "license": name(data, t[b"name"][0], 13)[:200], "file_sha256": hashlib.sha256(data).hexdigest()},
        "units_per_em": units_per_em,
        "advances": widths,
    }


if __name__ == "__main__":
    json.dump(measure(sys.argv[1], sys.argv[2]), sys.stdout, indent=1, ensure_ascii=False)
    sys.stdout.write("\n")
