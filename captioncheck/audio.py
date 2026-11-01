"""Analysis audio: 16 kHz mono 16-bit PCM, hashed so every finding can point at its samples.

Two ways in:
  * from_pcm24_stereo_48k(): raw 24-bit big-endian stereo PCM (an AIFF byte range).
    Downmix and decimation use integer arithmetic only, so the output, and every
    span hash taken from it, is bit-identical on any machine.
  * load(): any file ffmpeg can read. The decoder version is recorded with the
    hash, because lossy decoders are not guaranteed bit-exact across versions.
"""

from __future__ import annotations

import hashlib
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

RATE = 16_000

# 63-tap Blackman-windowed sinc low-pass (-6 dB at 7 kHz for 48 kHz input),
# quantized to integers summing to 2**15. Fixed here rather than computed, so
# no floating-point library difference can change the canonical samples.
DECIMATE_3_TAPS = np.array(
    [0, 0, 1, 2, -2, -10, -12, 0, 26, 43, 23, -39, -101, -92, 21, 178, 235, 81, -232, -463,
     -341, 175, 756, 859, 158, -1055, -1860, -1219, 1281, 4953, 8241, 9554, 8241, 4953, 1281,
     -1219, -1860, -1055, 158, 859, 756, 175, -341, -463, -232, 81, 235, 178, 21, -92, -101,
     -39, 23, 43, 26, 0, -12, -10, -2, 2, 1, 0, 0],
    dtype=np.int64,
)
INTEGER_DECODER = "captioncheck pcm24be-stereo-48k -> s16 mono 16k, integer FIR v1"


@dataclass
class Audio:
    samples: np.ndarray
    rate: int
    decoder: str
    offset: float = 0.0
    """Program time, in seconds, of the first sample."""

    def __post_init__(self) -> None:
        if self.samples.dtype != np.int16 or self.samples.ndim != 1:
            raise ValueError("analysis audio must be 1-D int16")
        self.sha256 = hashlib.sha256(self.samples.astype("<i2").tobytes()).hexdigest()

    @property
    def seconds(self) -> float:
        return len(self.samples) / self.rate

    def _bounds(self, start: float, end: float) -> tuple[int, int]:
        a = int(round((start - self.offset) * self.rate))
        b = int(round((end - self.offset) * self.rate))
        a = min(max(a, 0), len(self.samples))
        b = min(max(b, a), len(self.samples))
        return a, b

    def span_sha256(self, start: float, end: float) -> str:
        """SHA-256 of the little-endian int16 samples between two program times."""
        a, b = self._bounds(start, end)
        return hashlib.sha256(self.samples[a:b].astype("<i2").tobytes()).hexdigest()

    def level_dbfs(self, start: float, end: float) -> float:
        """RMS level of a span in dBFS; -120 for silence or an empty span."""
        a, b = self._bounds(start, end)
        return rms_dbfs(self.samples[a:b])

    def float32(self) -> np.ndarray:
        return self.samples.astype(np.float32) / 32768.0


def rms_dbfs(x: np.ndarray) -> float:
    if len(x) == 0:
        return -120.0
    ms = float(np.mean(np.square(x.astype(np.float64)))) / (32768.0**2)
    return max(-120.0, 10 * np.log10(ms)) if ms > 0 else -120.0


def envelope_dbfs(audio: Audio, hop: float = 0.01, window: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    """Short-term RMS level, one value per hop. Returns (program_times, dbfs)."""
    x = audio.samples.astype(np.float64) / 32768.0
    hop_n, win_n = int(hop * audio.rate), int(window * audio.rate)
    if len(x) < win_n:
        return np.array([]), np.array([])
    csum = np.concatenate([[0.0], np.cumsum(x * x)])
    starts = np.arange(0, len(x) - win_n + 1, hop_n)
    ms = (csum[starts + win_n] - csum[starts]) / win_n
    db = 10 * np.log10(np.maximum(ms, 1e-12))
    times = audio.offset + (starts + win_n / 2) / audio.rate
    return times, db


def pcm24_stereo_48k_to_mono16k(raw: bytes) -> np.ndarray:
    """24-bit big-endian interleaved stereo at 48 kHz -> int16 mono at 16 kHz, integers only."""
    if len(raw) % 6:
        raise ValueError("24-bit stereo PCM must be a whole number of 6-byte frames")
    b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 6).astype(np.int64)
    left = (b[:, 0] << 16) | (b[:, 1] << 8) | b[:, 2]
    right = (b[:, 3] << 16) | (b[:, 4] << 8) | b[:, 5]
    left -= (left & 0x800000) << 1
    right -= (right & 0x800000) << 1
    mono = left + right
    delay = (len(DECIMATE_3_TAPS) - 1) // 2
    y = np.convolve(mono, DECIMATE_3_TAPS)[delay : delay + len(mono) : 3]
    # mono is two 24-bit channels summed; taps sum to 2**15. 15 + 1 + 8 bits down to int16.
    out = (y + (1 << 23)) >> 24
    return np.clip(out, -32768, 32767).astype(np.int16)


def from_pcm24_stereo_48k(raw: bytes, offset: float = 0.0) -> Audio:
    return Audio(pcm24_stereo_48k_to_mono16k(raw), RATE, INTEGER_DECODER, offset)


def write_wav(path: str | Path, audio: Audio) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(audio.rate)
        w.writeframes(audio.samples.astype("<i2").tobytes())


def _ffmpeg_version() -> str:
    out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True).stdout
    return out.splitlines()[0].split(" Copyright")[0]


def load(path: str | Path, offset: float = 0.0, decoder: str | None = None) -> Audio:
    """Load analysis audio. A 16 kHz mono 16-bit WAV is read as is; anything else goes through ffmpeg."""
    p = Path(path)
    if p.suffix.lower() == ".wav":
        with wave.open(str(p), "rb") as w:
            if (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, RATE):
                samples = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.int16)
                return Audio(samples, RATE, decoder or f"wav s16 mono {RATE}", offset)
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(p), "-map", "0:a:0",
           "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"]
    pcm = subprocess.run(cmd, capture_output=True, check=True).stdout
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.int16)
    return Audio(samples, RATE, f"{_ffmpeg_version()} -ac 1 -ar {RATE} s16le", offset)
