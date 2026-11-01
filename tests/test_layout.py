import json
from pathlib import Path

import pytest

from captioncheck.layout import DISPLAYS, glyph_table, wrap

TABLE = glyph_table("liberation-sans-regular")


def test_glyphs_are_not_characters():
    wide, _ = TABLE.width_px("WWWWW", 54)
    narrow, _ = TABLE.width_px("iiiii", 54)
    assert wide > 4 * narrow


def test_42_characters_fit_or_not_depending_on_the_letters():
    tv = DISPLAYS["tv-1080p"]
    assert TABLE.width_px("W" * 42, tv.font_px)[0] > tv.usable_px
    assert TABLE.width_px("i" * 42, tv.font_px)[0] < tv.usable_px


def test_a_line_that_fits_a_tv_overflows_a_phone_with_large_type():
    line = "Why don't you just admit that you're freaked out"
    assert TABLE.width_px(line, DISPLAYS["tv-1080p"].font_px)[0] < DISPLAYS["tv-1080p"].usable_px
    assert TABLE.width_px(line, DISPLAYS["phone-large"].font_px)[0] > DISPLAYS["phone-large"].usable_px
    lines = wrap(line, DISPLAYS["phone-large"])
    assert len(lines) == 2 and " ".join(lines) == line
    assert all(TABLE.width_px(x, 18)[0] <= DISPLAYS["phone-large"].usable_px for x in lines)


def test_unmeasured_glyph_counts_as_a_full_em():
    w, missing = TABLE.width_px("字", 20)
    assert missing == 1 and w == pytest.approx(20)


def test_model_ref_names_the_table_and_its_hash():
    ref = TABLE.model_ref
    assert ref["kind"] == "glyphs" and ref["id"] == "glyphs:liberation-sans-regular" and len(ref["version"]) == 16


FONT = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf")


@pytest.mark.skipif(not FONT.exists(), reason="Liberation Sans not installed")
def test_shipped_table_matches_the_font_it_was_measured_from():
    import importlib.util
    spec = importlib.util.spec_from_file_location("glyph_table", Path(__file__).parent.parent / "scripts" / "glyph_table.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    shipped = json.loads((Path(__file__).parent.parent / "captioncheck/data/glyphs/liberation-sans-regular.json").read_text())
    fresh = mod.measure(str(FONT), "liberation-sans-regular")
    if fresh["font"]["file_sha256"] != shipped["font"]["file_sha256"]:
        pytest.skip("a different build of Liberation Sans is installed")
    assert fresh == shipped
