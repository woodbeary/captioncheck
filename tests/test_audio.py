import hashlib

import numpy as np

from captioncheck import audio


def _pcm24_stereo(left: np.ndarray, right: np.ndarray) -> bytes:
    frames = np.stack([left, right], axis=1).astype(np.int64).reshape(-1)
    u = frames & 0xFFFFFF
    return np.stack([(u >> 16) & 0xFF, (u >> 8) & 0xFF, u & 0xFF], axis=1).astype(np.uint8).tobytes()


def test_dc_comes_through_exactly():
    x = np.full(48_000, 1 << 20)
    out = audio.pcm24_stereo_48k_to_mono16k(_pcm24_stereo(x, x))
    assert len(out) == 16_000
    assert np.all(out[100:-100] == 4096)


def test_passband_kept_and_alias_band_removed():
    n = np.arange(48_000 * 2)
    def level(freq):
        x = np.round(0.5 * (1 << 23) * np.sin(2 * np.pi * freq * n / 48_000))
        out = audio.pcm24_stereo_48k_to_mono16k(_pcm24_stereo(x, x))
        return audio.rms_dbfs(out[1000:-1000])
    half_scale_sine = 20 * np.log10(0.5 / np.sqrt(2))
    assert abs(level(1000) - half_scale_sine) < 0.1
    assert level(10_000) < level(1000) - 60


def test_integer_path_is_pinned_bit_for_bit():
    # Integer-only input; if this hash changes, analysis audio (and every span hash) changed.
    n = np.arange(48_000, dtype=np.int64)
    left = ((n * 2654435761) % (1 << 24)) - (1 << 23)
    right = ((n * 40503 + 12345) % (1 << 24)) - (1 << 23)
    out = audio.pcm24_stereo_48k_to_mono16k(_pcm24_stereo(left, right))
    assert hashlib.sha256(out.astype("<i2").tobytes()).hexdigest() == PINNED


PINNED = "b20b28afa8cc12d9d3578031c7f83695d8f42f739d089dcb3b2d741e90f84342"


def test_span_hash_moves_with_one_sample(program):
    a = program.audio
    h = a.span_sha256(1.0, 2.0)
    assert h == a.span_sha256(1.0, 2.0)
    changed = a.samples.copy()
    changed[int(1.5 * a.rate)] ^= 1
    b = audio.Audio(changed, a.rate, a.decoder, a.offset)
    assert b.span_sha256(1.0, 2.0) != h and b.span_sha256(3.0, 4.0) == a.span_sha256(3.0, 4.0)
    assert b.sha256 != a.sha256


def test_offset_maps_program_time_to_samples(program):
    shifted = audio.Audio(program.audio.samples, audio.RATE, "x", offset=100.0)
    assert shifted.span_sha256(101.0, 102.0) == program.audio.span_sha256(1.0, 2.0)
    assert shifted.level_dbfs(110.0, 110.4) > -10


def test_wav_round_trip(tmp_path, program):
    p = tmp_path / "a.wav"
    audio.write_wav(p, program.audio)
    back = audio.load(p, offset=0.0)
    assert back.sha256 == program.audio.sha256
