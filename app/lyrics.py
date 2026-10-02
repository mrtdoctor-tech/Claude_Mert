"""Lyrics (3.49, Asiye_Isterler.txt §4): a draft transcript of the sung words at the end of the music report.

Not rewritten: HourGlow's own pipeline Scripts\\analiz\\analiz.py is loaded from Drive each time (like hg_bpm.py) and its
functions do the work: separate_vocals (Demucs two stems, run with this Python), transcribe (openai-whisper on the GPU;
language=None → Whisper detects it), flatten_words, is_adlib_segment, find_gaps (no-lyric spans of at least
DEFAULT_GAP_THRESHOLD seconds; ad-libs are not lyrics). Rules from HourGlow's 03.08.2026 test: Demucs is required
(Whisper hallucinates on the full mix) and the model is medium (large on this GPU gives "Thank you" ×7).
The stems go to a temporary folder and are deleted (never written into Drive).
"""

import gc
import importlib.util
import logging
import shutil
import tempfile
import warnings
from pathlib import Path

from . import stt

log = logging.getLogger("asistan.lyrics")

MODEL = "medium"        # never "large" here: broken on this GPU (analiz.py MODEL SECIMI)
VOCAL_LEVEL_DB = -40.0  # a 0.5 s block of the vocal stem louder than this counts as singing
VOCAL_MIN_SHARE = 0.03  # less singing than this share of the song → instrumental, Whisper is not run
NOTE = "  Taslak transkript — resmi söz metni Suno'dan alınır."
LANGUAGES = {"en": "İngilizce", "es": "İspanyolca", "tr": "Türkçe", "zu": "Zuluca", "pt": "Portekizce",
             "fr": "Fransızca", "de": "Almanca", "it": "İtalyanca", "xh": "Xhosaca", "sn": "Şonaca",
             "sw": "Svahili", "af": "Afrikaanca", "ja": "Japonca", "ko": "Korece", "ar": "Arapça"}


def _analiz(folder: Path | None):
    path = folder.parent / "analiz" / "analiz.py" if folder else None
    if not path or not path.is_file():
        raise FileNotFoundError(f"analiz.py bulunamadı ({path})")
    spec = importlib.util.spec_from_file_location("hg_analiz", path)
    module = importlib.util.module_from_spec(spec)
    with warnings.catch_warnings():
        spec.loader.exec_module(module)
    return module


def _time(seconds: float) -> str:
    seconds = max(0, int(seconds))  # floor: a line that starts at 0:12.8 is found at 0:12
    return f"{seconds // 60}:{seconds % 60:02d}"


def _singing_share(path: str) -> float:
    import numpy as np
    import soundfile

    audio, rate = soundfile.read(path, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    step = rate // 2
    blocks = [float(np.sqrt(np.mean(mono[i:i + step] ** 2))) for i in range(0, mono.size - step + 1, step)]
    if not blocks:
        return 0.0
    loud = sum(1 for b in blocks if 20 * np.log10(max(b, 1e-9)) > VOCAL_LEVEL_DB)
    return loud / len(blocks)


def _free_gpu():
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def section(path: Path, duration: float, folder: Path | None) -> tuple[list[str], dict]:
    """SÖZLER report lines + {"language": "es" | None, "instrumental": bool}."""
    lines, info = ["SÖZLER", NOTE], {"language": None, "instrumental": False}
    hg = _analiz(folder)
    temp = tempfile.mkdtemp(prefix="asiye_stem_")
    try:
        vocals = hg.separate_vocals(str(path), temp)
        if not vocals:
            lines.append("  Vokal ayrılamadı (Demucs), sözler çıkarılmadı: tam mix'te Whisper söz uyduruyor.")
            return lines, info
        share = _singing_share(vocals)
        if share < VOCAL_MIN_SHARE:
            info["instrumental"] = True
            lines.append(f"  Enstrümantal, söz yok (ayrılan vokal kanalında ses olan süre: %{round(share * 100)}).")
            return lines, info
        with warnings.catch_warnings():  # "Failed to launch Triton kernels": harmless, slower DTW on Windows
            warnings.simplefilter("ignore", UserWarning)
            result = hg.transcribe(vocals, MODEL, language=None)
    finally:
        shutil.rmtree(temp, ignore_errors=True)
        _free_gpu()

    code = result.get("language") or ""
    segments = []
    for seg in result.get("segments", []):
        text = stt.clean(seg.get("text", ""))  # "Thanks for watching", "Altyazı M.K." …
        if text:
            segments.append((seg, text))
    lyric_words, _ = hg.split_words_by_adlib({"segments": [s for s, _ in segments]})
    if not lyric_words:
        info["instrumental"] = True
        lines.append("  Enstrümantal, söz yok (Whisper ayrılan vokalde sözcük bulamadı).")
        return lines, info
    info["language"] = code
    lines.append(f"  Dil: {LANGUAGES.get(code, code or 'bilinmiyor')} ({code}, Whisper algıladı; şarkının başına bakar, "
                 "karışık dilli şarkıda diğer dil yanlış yazılabilir)")
    lines.append(f"  Model: whisper-{MODEL}, izole vokal (Demucs)")
    lines.append("")
    for seg, text in segments:
        lines.append(f"  {_time(seg['start'])}  {text}" + ("  [ad-lib]" if hg.is_adlib_segment(seg) else ""))

    kept = {"segments": [s for s, _ in segments]}
    gaps, adlibs = hg.find_gaps(kept, hg.flatten_words(kept), hg.DEFAULT_GAP_THRESHOLD, duration)
    lines += ["", f"  Vokalsiz aralıklar (≥ {hg.DEFAULT_GAP_THRESHOLD:.0f} sn; ad-lib söz sayılmaz):"]
    if not gaps:
        lines.append("  yok")
    for start, end, length in gaps:
        lines.append(f"  {_time(start)} – {_time(end)}  ({round(length)} sn)")
        for a_start, a_end in hg.adlibs_in_gap(start, end, adlibs):
            lines.append(f"      ad-lib: {_time(a_start)} – {_time(a_end)}")
    return lines, info
