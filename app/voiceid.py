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
# Real voices (2026-09-29, home PC): Mert's short spoken messages scored 0.36-0.55 against a voiceprint read aloud
# with 0.91 consistency; Sezin 0.66; nobody was ever matched to the wrong person. 0.40 turned Mert into a guest once.
THRESHOLD = 0.33
MARGIN = 0.08  # the best match must beat the next profile by this much, or it is not trusted
ADAPT_MIN = 0.50  # a clearly recognised message is blended into the voiceprint (conversation voice != reading voice)
ADAPT_WEIGHT = 0.1
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


def identify(path: str) -> dict:
    """{"name": recognised person or None, "score": best similarity, "scores": {name: similarity}}.

    score None means too little speech to tell anything.
    """
    vector = embed_file(path)
    if vector is None:
        return {"name": None, "score": None, "scores": {}}
    speakers = db.list_speakers()
    scores = {s["name"]: float(vector @ np.array(s["embedding"], dtype=np.float32)) for s in speakers}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_name, best = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else -1.0
    name = best_name if best >= THRESHOLD and best - second >= MARGIN else None
    if name and best >= ADAPT_MIN and best - second >= 2 * MARGIN:
        profile = next(s for s in speakers if s["name"] == name)
        blended = (1 - ADAPT_WEIGHT) * np.array(profile["embedding"], dtype=np.float32) + ADAPT_WEIGHT * vector
        db.save_speaker(name, (blended / np.linalg.norm(blended)).tolist(), profile["is_admin"])
    return {"name": name, "score": round(best, 3), "scores": {k: round(v, 3) for k, v in ranked}}


def describe(scores: dict) -> str:
    """"Mert 0,51 · Sezin 0,12" for the security log."""
    return " · ".join(f"{k} {v:.2f}".replace(".", ",") for k, v in scores.items())


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
