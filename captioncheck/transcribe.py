"""Word timings from Whisper via faster-whisper, offline once the model is cached.

The model gets the analysis samples themselves (not a path or URL), so the
audio hash in the transcript is the hash of what the model heard. Decoding is
deterministic (temperature 0, no previous-text conditioning, no VAD), and the
model repository revision is recorded with every transcript.
"""

from __future__ import annotations

import os
from pathlib import Path

from .audio import Audio
from .words import Transcript, Word

PARAMS = {"language": "en", "beam_size": 5, "temperature": 0.0, "word_timestamps": True,
          "condition_on_previous_text": False, "vad_filter": False}


def transcribe(audio: Audio, model: str = "small.en", offline: bool = False,
               compute_type: str = "int8") -> Transcript:
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        import ctranslate2
        import faster_whisper
        from faster_whisper import WhisperModel
        from faster_whisper.utils import download_model
    except ImportError as e:
        raise SystemExit("live transcription needs: pip install 'captioncheck[whisper]'") from e

    model_dir = download_model(model, local_files_only=offline)
    whisper = WhisperModel(model_dir, device="cpu", compute_type=compute_type)
    segments, _ = whisper.transcribe(audio.float32(), **PARAMS)
    words = [Word(w.word.strip(), float(w.start), float(w.end), float(w.probability))
             for seg in segments for w in (seg.words or []) if w.word.strip()]
    meta = {"backend": "faster-whisper", "backend_version": faster_whisper.__version__,
            "ctranslate2": ctranslate2.__version__, "name": model,
            "repo": f"Systran/faster-whisper-{model}", "revision": Path(model_dir).name,
            "compute_type": compute_type, "device": "cpu"}
    return Transcript(audio.sha256, words, meta, dict(PARAMS))
