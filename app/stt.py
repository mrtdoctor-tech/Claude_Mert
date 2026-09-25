"""Offline speech-to-text with faster-whisper (the model is downloaded once, on first use)."""

import threading

_lock = threading.Lock()
_model = None
_model_name = None


def transcribe(path: str, model_name: str, language: str | None) -> str:
    global _model, _model_name
    with _lock:
        if _model is None or _model_name != model_name:
            from faster_whisper import WhisperModel

            _model = WhisperModel(model_name, device="cpu", compute_type="int8")
            _model_name = model_name
        segments, _ = _model.transcribe(path, language=language or None, vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()
