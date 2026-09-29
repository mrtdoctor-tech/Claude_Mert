"""Speaker identification ("voiceprints"), fully offline with sherpa-onnx.

Each enrolled person has one voiceprint: the average of the embeddings of a few recorded sentences.
A spoken message is compared with every voiceprint (cosine similarity); the best match above THRESHOLD wins.

Model choice (tested on sherpa-onnx's four-speaker recording, 2026-09-29): 3D-Speaker ERes2Net gave
same-speaker similarity >= 0.44 and different-speaker <= 0.26, clearly better separated than WeSpeaker
ResNet34 or NeMo TitaNet-small. THRESHOLD sits between those; tune it with real voices (scores are logged).
"""

import logging
import threading

import httpx
import numpy as np

from . import config, db

log = logging.getLogger("asistan.voiceid")

MODEL_NAME = "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
MODEL_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/{MODEL_NAME}"
MODEL_PATH = config.SETTINGS_DIR / "models" / MODEL_NAME
SAMPLE_RATE = 16000
THRESHOLD = 0.40
MIN_SPEECH_SECONDS = 0.8  # shorter speech says too little about the voice; the identity is left unchanged

_lock = threading.Lock()
_extractor = None


def _ensure_model():
    if MODEL_PATH.exists():
        return
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    log.info("Ses parmak izi modeli indiriliyor (yaklaşık 40 MB, bir kez): %s", MODEL_URL)
    tmp = MODEL_PATH.with_suffix(".part")
    with httpx.stream("GET", MODEL_URL, follow_redirects=True, timeout=httpx.Timeout(300.0, connect=15.0)) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    tmp.replace(MODEL_PATH)


def _get_extractor():
    global _extractor
    if _extractor is None:
        import sherpa_onnx

        _ensure_model()
        cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(MODEL_PATH), num_threads=2, provider="cpu")
        if not cfg.validate():
            raise RuntimeError("Ses parmak izi modeli açılamadı")
        _extractor = sherpa_onnx.SpeakerEmbeddingExtractor(cfg)
    return _extractor


def warm_up():
    """Download/load the model ahead of time (called when the microphone opens)."""
    with _lock:
        _get_extractor()


def _speech_only(samples: np.ndarray) -> np.ndarray:
    """Drop silent 30 ms frames so pauses do not dilute the voiceprint."""
    frame = int(0.03 * SAMPLE_RATE)
    n = len(samples) // frame
    if n == 0:
        return samples[:0]
    frames = samples[: n * frame].reshape(n, frame)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    loud = rms > max(0.005, 0.05 * float(rms.max()))
    return frames[loud].reshape(-1)


def embed_file(path: str) -> np.ndarray | None:
    """Normalized voiceprint of a recording, or None if it holds too little speech."""
    from faster_whisper import decode_audio

    samples = _speech_only(decode_audio(path, sampling_rate=SAMPLE_RATE))
    if len(samples) < MIN_SPEECH_SECONDS * SAMPLE_RATE:
        return None
    with _lock:
        extractor = _get_extractor()
        stream = extractor.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples)
        stream.input_finished()
        if not extractor.is_ready(stream):
            return None
        vector = np.array(extractor.compute(stream), dtype=np.float32)
    return vector / np.linalg.norm(vector)


def identify(path: str) -> tuple[str | None, float | None]:
    """(name of the recognised person or None, best similarity) — (None, None) if too little speech."""
    vector = embed_file(path)
    if vector is None:
        return None, None
    best_name, best_score = None, -1.0
    for speaker in db.list_speakers():
        score = float(vector @ np.array(speaker["embedding"], dtype=np.float32))
        if score > best_score:
            best_name, best_score = speaker["name"], score
    return (best_name if best_score >= THRESHOLD else None), round(best_score, 3)


def enroll(name: str, paths: list[str], is_admin: bool) -> dict:
    """Save a voiceprint from several recordings. Returns how consistent the samples were."""
    vectors = [v for v in (embed_file(p) for p in paths) if v is not None]
    if len(vectors) < 2:
        raise ValueError("Kayıtlarda yeterince konuşma duyulmadı. Cümleleri biraz daha yüksek sesle tekrar oku.")
    mean = np.mean(vectors, axis=0)
    mean /= np.linalg.norm(mean)
    consistency = min(float(v @ mean) for v in vectors)
    db.save_speaker(name, mean.tolist(), is_admin)
    return {"samples": len(vectors), "consistency": round(consistency, 3)}
