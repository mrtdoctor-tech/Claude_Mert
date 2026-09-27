"""Offline speech-to-text with faster-whisper (the model is downloaded once, on first use)."""

import threading

_lock = threading.Lock()
_model = None
_model_name = None


def load(model_name: str):
    global _model, _model_name
    with _lock:
        if _model is None or _model_name != model_name:
            from faster_whisper import WhisperModel

            _model = WhisperModel(model_name, device="cpu", compute_type="int8")
            _model_name = model_name
        return _model


def transcribe(path: str, model_name: str, language: str | None) -> str:
    model = load(model_name)
    with _lock:
        segments, _ = model.transcribe(path, language=language or None, vad_filter=True, beam_size=1)
        return " ".join(s.text.strip() for s in segments).strip()
