"""Folder analysis (3.26): music and pictures dropped into the "Asiye" folder of HourGlow Music.

"Asiye klasöründeki dosyaları analiz et" in the chat: every music and picture file in the folder that has no report
yet (or changed since) is analyzed, and the result is written next to it as "<file>.analiz.txt". Everything runs on
this computer: the measurements with librosa / pyloudnorm / Pillow, the picture description with the local model
(gemma3 can see pictures). Only people recognized by voice or passcode can use it (the folder is theirs), not guests.

Music: length, format, tags, loudness (LUFS, peak, RMS, dynamics, clipping), tempo (BPM), key, brightness, stereo
width, silence at the start/end, sections by loudness. 3.45: no model comment on music (it called -1.6 dBTP "safe" and
suggested compression for more dynamics); the report is measurements only, in a fixed order (Asiye_Isterler.txt §3).
3.47: a TARGET CHECK section right after DOSYA compares the measurements with the HourGlow mastering rules (TARGETS).
3.48: SES YÜKSEKLİĞİ shows values only (verdicts live in HEDEF KONTROLÜ); the tempo is cross-checked with HourGlow's
hg_bpm.py (BPM_DIFF_MAX, BPM_STABLE_MIN; Asiye_Isterler.txt §6).
3.49: SÖZLER at the end — lyrics.py, with HourGlow's analiz.py (Demucs + Whisper medium; §4).
3.51: one command runs every stage in order and reports each stage on the screen (Asiye_Isterler.txt §2).
Pictures: size, format, EXIF (camera, date, settings), brightness, contrast, saturation, sharpness, dominant colors,
warm/cool, and what the model sees in it (description, mood, text in the picture).
"""

import asyncio
import base64
import io
import logging
import math
import os
import re
from datetime import datetime
from pathlib import Path

from . import config, identity, llm, lyrics

log = logging.getLogger("asistan.analysis")

MUSIC = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif", ".opus", ".wma"}
PICTURES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
REPORT_SUFFIX = ".analiz.txt"
ANALYSIS_RATE = 22050  # tempo / key / brightness are measured on a mono copy at this rate
KEYS = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
KEYS_EN = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Krumhansl-Schmuckler key profiles
MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

# 3.47: target check (Asiye_Isterler.txt §5). The only place the limits live.
# Kaynak: CLAUDE.md > Mastering (ileride _Referans\Mastering_Kurallari.txt)
TARGETS = {
    "lufs": -14.5,          # integrated loudness aimed at
    "lufs_low": -16.0,      # UYARI below this
    "lufs_high": -13.0,     # UYARI above this
    "true_peak_max": -3.0,  # dBTP; UYARI above this
    "lra_low": 4.0,         # LU; UYARI outside 4-7 ("genre character" note)
    "lra_high": 7.0,
    "clipped_max": 0,       # clipped samples
    "bits": 24,             # format: 24-bit / 44.1 kHz / stereo; UYARI when mono or 16-bit (or less)
    "rate": 44100,
}
BPM_DIFF_MAX = 2.0     # 3.48: Asiye vs hg_bpm.py; more is UYARI (Asiye_Isterler.txt §6)
BPM_STABLE_MIN = 0.7   # hg_bpm "kararlilik" below this is pointed out
LOSSY = {"mp3", "mp3float", "aac", "opus", "vorbis", "wmav1", "wmav2", "wmapro"}


def folder() -> Path | None:
    """The folder from Settings, or the HourGlow Music "Asiye" folder in Google Drive, found by itself."""
    chosen = (config.load().get("analysis_folder") or "").strip().strip('"')
    if chosen:
        return Path(os.path.expandvars(chosen))
    home = Path.home()
    for base in [*home.glob("My Drive*"), *home.glob("Google Drive*"), Path("G:/My Drive"), Path("G:/Drive'ım")]:
        candidate = base / "HourGlowMusic" / "Scripts" / "Asiye"
        if candidate.is_dir():
            return candidate
    return None


# Chat commands

_FOLDER_WORDS = r"(klasör|klasor|dosya|şarkı|şarkıları|müzik|parça|resim|fotoğraf|görsel|kapak)"
_COMMAND = re.compile(rf"\banaliz\w*\b.*\b{_FOLDER_WORDS}|\b{_FOLDER_WORDS}\w*\b.*\banaliz\w*")
_OPEN = re.compile(r"\b(analiz|asiye)\s+klasör\w*\s+(aç|göster)")
_DO = re.compile(r"analiz\w*\s+(et|yap|başla|eder|yapar)|analiz\w*\s*(lütfen)?\s*[.!?]*$")
_AGAIN = re.compile(r"\b(yeniden|tekrar|baştan|hepsini|tümünü|tamamını)\b")
_BARE_WORDS = {"hepsini", "tümünü", "tamamını", "hepsi", "yeniden", "tekrar", "baştan", "et", "eder", "yap", "yapar",
               "misin", "mısın", "lütfen", "asiye", "merhaba", "bunları", "onları", "şunları", "bir", "de", "da"}
_QUESTION = re.compile(r"\b(nasıl|nedir|neden|ne demek)\b")


def is_command(text: str) -> bool:
    low = text.replace("I", "ı").replace("İ", "i").lower()
    if len(low) > 120 or _QUESTION.search(low):
        return False
    # 3.27: "Hepsini yeniden analiz et." has no folder word; it went to the model, which made up four songs.
    rest = set(re.findall(r"[\wçğıöşü]+", low)) - _BARE_WORDS
    short_again = bool(_AGAIN.search(low) and _DO.search(low) and not {w for w in rest if not w.startswith("analiz")})
    return bool(_OPEN.search(low) or (_COMMAND.search(low) and _DO.search(low)) or short_again)


def wants_open(text: str) -> bool:
    return bool(_OPEN.search(text.replace("I", "ı").replace("İ", "i").lower()))


def waiting_files(again: bool = False) -> list[Path]:
    where = folder()
    if not where or not where.is_dir():
        return []
    found = []
    for path in sorted(where.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.suffix.lower() not in MUSIC | PICTURES:
            continue
        report = report_path(path)
        if again or not report.exists() or report.stat().st_mtime < path.stat().st_mtime:
            found.append(path)
    return found


def report_path(path: Path) -> Path:
    return path.with_name(path.name + REPORT_SUFFIX)


def refusal(owner: str) -> str | None:
    if owner == identity.GUEST:
        return "Klasör analizi yalnızca sesinden ya da şifresinden tanıdığım kişiler için. Önce bir cümle söyle ya da şifreni yaz."
    where = folder()
    if not where:
        return ("Analiz klasörünü bulamadım. Google Drive'da \"HourGlowMusic\\Scripts\\Asiye\" klasörü açık mı? Başka bir "
                "klasör kullanmak istersen ⚙️ Ayarlar → 🌐 Bağlantılar → \"Analiz klasörü\"ne yolunu yapıştır.")
    if not where.is_dir():
        return f"Analiz klasörü bulunamadı: {where}. ⚙️ Ayarlar → 🌐 Bağlantılar → \"Analiz klasörü\"nü kontrol et."
    return None


# Helpers

def _db(value: float) -> float:
    return 20 * math.log10(max(value, 1e-9))


def _time(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _size(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{n / 1024:.0f} KB"


def _num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


# Music

def _decode(path: Path):
    """(samples float32 [channels, n], sample rate, info dict) with PyAV (comes with faster-whisper; reads mp3/m4a too)."""
    import av
    import numpy as np

    info = {}
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        info["codec"] = stream.codec_context.name
        info["bitrate"] = container.bit_rate or stream.bit_rate
        info["tags"] = {k.lower(): v for k, v in {**(container.metadata or {}), **(stream.metadata or {})}.items()}
        rate = stream.rate or stream.codec_context.sample_rate
        info["bits"] = _bits(stream.codec_context)
        channels = stream.codec_context.channels or 1
        resampler = av.AudioResampler(format="fltp", layout="stereo" if channels > 1 else "mono", rate=rate)
        parts = []
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                parts.append(out.to_ndarray())
        for out in resampler.resample(None):
            parts.append(out.to_ndarray())
    if not parts:
        raise ValueError("ses okunamadı")
    samples = np.concatenate(parts, axis=1).astype("float32")
    info["channels"] = samples.shape[0]
    return samples, rate, info


def _bits(codec) -> int | None:
    """Bit depth of the stored audio: pcm_s24le → 24, 16-bit sample format → 16; None for lossy or unknown (FLAC in
    a 32-bit sample format may hold 24-bit audio, which PyAV does not tell)."""
    found = re.fullmatch(r"pcm_[suf](\d+)\w*", codec.name or "")
    if found:
        return int(found.group(1))
    if codec.name in LOSSY:
        return None
    bits = getattr(codec.format, "bits", None)
    return bits if bits and bits <= 16 else None


def target_check(info: dict, rate: int, lufs: float | None, tp_db: float | None, lra: float | None,
                 clipped: int) -> tuple[list[str], int]:
    """3.47: TAMAM / UYARI per mastering rule (TARGETS); returns (report lines, number of warnings)."""
    t = TARGETS
    rows = []
    if lufs is None:
        rows.append(("?", "Integrated LUFS", "ölçülemedi"))
    else:
        ok = t["lufs_low"] <= lufs <= t["lufs_high"]
        rows.append(("TAMAM" if ok else "UYARI", "Integrated LUFS",
                     f"{_num(lufs)} (hedef ~{_num(t['lufs'])}, aralık {_num(t['lufs_low'])} … {_num(t['lufs_high'])})"))
    if tp_db is None:
        rows.append(("?", "True peak", "ölçülemedi"))
    else:
        rows.append(("TAMAM" if tp_db <= t["true_peak_max"] else "UYARI", "True peak",
                     f"{_num(tp_db)} dBTP (en çok {_num(t['true_peak_max'])} dBTP)"))
    if lra is None:
        rows.append(("?", "LRA", "ölçülemedi"))
    else:
        ok = t["lra_low"] <= lra <= t["lra_high"]
        rows.append(("TAMAM" if ok else "UYARI", "LRA", f"{_num(lra)} LU (hedef {_num(t['lra_low'], 0)}–"
                     f"{_num(t['lra_high'], 0)} LU)" + ("" if ok else " — tür karakteri olabilir")))
    rows.append(("TAMAM" if clipped <= t["clipped_max"] else "UYARI", "Kırpılan örnek",
                 f"{clipped} (hedef {t['clipped_max']})"))
    bits, mono = info.get("bits"), info["channels"] < 2
    shape = (f"{bits}-bit" if bits else "kayıplı biçim (bit derinliği yok)" if info["codec"] in LOSSY
             else "bit derinliği bilinmiyor") + f" / {_num(rate / 1000)} kHz / {'mono' if mono else 'stereo'}"
    problems = (["mono (Studio One varsayılanı bazen mono veriyor)"] if mono else []) + (
        [f"{bits}-bit"] if bits and bits <= 16 else [])
    note = (" — " + ", ".join(problems)) if problems else (
        f" (hedef {t['bits']}-bit / {_num(t['rate'] / 1000)} kHz / stereo)"
        if bits != t["bits"] or rate != t["rate"] else "")
    rows.append(("UYARI" if problems else "TAMAM", "Biçim", shape + note))
    warnings = sum(1 for r in rows if r[0] == "UYARI")
    lines = ["HEDEF KONTROLÜ" + (f" — {warnings} uyarı" if warnings else " — hepsi tamam")]
    lines += [f"  {status:<5}  {name}: {text}" for status, name, text in rows]
    return lines, warnings


def _hg_bpm():
    """3.48: HourGlow's own BPM tool (Scripts\\hg_olcum\\hg_bpm.py), loaded from Drive each time — not copied, so a fix
    there is used here too. Its import silences warnings globally; catch_warnings keeps that inside the import."""
    import importlib.util
    import warnings

    where = folder()
    path = where.parent / "hg_olcum" / "hg_bpm.py" if where else None
    if not path or not path.is_file():
        raise FileNotFoundError(f"hg_bpm.py bulunamadı ({path})")
    spec = importlib.util.spec_from_file_location("hg_bpm", path)
    module = importlib.util.module_from_spec(spec)
    with warnings.catch_warnings():
        spec.loader.exec_module(module)
    return module


def bpm_cross_check(tempo: float, y, rate: int) -> tuple[list[str], bool]:
    """3.48 (Asiye_Isterler.txt §6): hg_bpm.py is the primary tool; both values are written, a difference over
    BPM_DIFF_MAX is UYARI (half / double time named), a stability under BPM_STABLE_MIN is pointed out.
    Returns (report lines, warning?)."""
    import warnings

    try:
        hg = _hg_bpm()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = hg.olc_sinyal(y, rate)  # same mono 22 050 Hz signal hg_bpm.olc() would load; band 80-160
        flag = hg.bayrak(result)
    except Exception as e:
        log.warning("hg_bpm.py çalıştırılamadı: %s", e)
        return [f"  Tempo (hg_bpm.py): ölçülemedi — {e}"], False
    bpm, stable = result["bpm"], result["kararlilik"]
    if not math.isfinite(bpm):
        return [f"  Tempo (hg_bpm.py): ölçülemedi (durum {flag})"], False
    lines = [f"  Tempo (hg_bpm.py, birincil): {_num(bpm)} BPM — kararlılık {_num(stable, 2)}, durum {flag}"
             + (f", ikinci aday {_num(result['aday2'])}" if math.isfinite(result.get("aday2", float("nan"))) else "")]
    diff = abs(tempo - bpm)
    warning = bool(diff > BPM_DIFF_MAX)
    relation = next((name for factor, name in ((0.5, "yarısı (half-time)"), (2.0, "iki katı (double-time)"))
                     if abs(tempo - bpm * factor) <= BPM_DIFF_MAX), "")
    lines.append(f"  BPM karşılaştırması: {'UYARI' if warning else 'TAMAM'} — Asiye {_num(tempo)}, hg_bpm {_num(bpm)}, "
                 f"fark {_num(diff)} BPM"
                 + (f"; Asiye'nin değeri hg_bpm'in {relation}" if warning and relation else "")
                 + (f" (en çok {_num(BPM_DIFF_MAX, 0)})" if warning else ""))
    if stable < BPM_STABLE_MIN:
        lines.append(f"  Not: hg_bpm kararlılığı {_num(stable, 2)} (< {_num(BPM_STABLE_MIN, 1)}): tempo değişken ya da "
                     "belirsiz, Moises'te elle doğrula")
    return lines, warning


def true_peak(samples, oversample: int = 4) -> float:
    """3.44: inter-sample peak (ITU-R BS.1770 true peak): each channel upsampled 4x with a polyphase low-pass filter,
    in 10-second pieces with overlap so memory stays small. Returns the linear peak (dBTP = 20·log10)."""
    import numpy as np
    from scipy.signal import resample_poly

    piece, pad = 441_000, 256
    peak = 0.0
    for channel in samples:
        for start in range(0, channel.size, piece):
            lo, hi = max(0, start - pad), min(channel.size, start + piece + pad)
            up = resample_poly(channel[lo:hi].astype("float64"), oversample, 1)
            keep = up[(start - lo) * oversample:(start - lo + min(piece, channel.size - start)) * oversample]
            if keep.size:
                peak = max(peak, float(np.max(np.abs(keep))))
    return peak


def loudness_range(samples, rate: int) -> float | None:
    """3.44: EBU R128 loudness range (EBU Tech 3342): K-weighted short-term loudness (3 s windows every 0.1 s),
    absolute gate -70 LUFS, relative gate 20 LU below their power mean, LRA = 95th − 10th percentile, in LU.
    None when the piece is shorter than one window."""
    import numpy as np
    import pyloudnorm

    meter = pyloudnorm.Meter(rate)
    power = np.zeros(samples.shape[1], dtype="float64")
    for channel in samples:  # stereo/mono: every channel weight is 1.0
        z = channel.astype("float64")
        for stage in meter._filters.values():  # K-weighting (high shelf + high pass), as pyloudnorm's integrated LUFS
            z = stage.apply_filter(z)
        power += z * z
    window, hop = int(3 * rate), int(0.1 * rate)
    if power.size < window:
        return None
    total = np.concatenate(([0.0], np.cumsum(power)))
    starts = np.arange(0, power.size - window + 1, hop)
    mean = (total[starts + window] - total[starts]) / window
    loud = -0.691 + 10 * np.log10(np.maximum(mean, 1e-20))
    gated = loud[loud > -70]
    if gated.size < 2:
        return None
    relative = -0.691 + 10 * np.log10(np.mean(10 ** ((gated + 0.691) / 10))) - 20
    gated = gated[gated > relative]
    if gated.size < 2:
        return None
    return float(np.percentile(gated, 95) - np.percentile(gated, 10))


def music_report(path: Path, step=lambda name: None) -> tuple[list[str], dict]:
    """step(name) is called when a stage starts (3.51: progress on the screen); it changes nothing in the report."""
    import librosa
    import numpy as np

    samples, rate, info = _decode(path)
    mono = samples.mean(axis=0)
    duration = mono.size / rate
    lines, facts = [], {}

    lines += ["DOSYA", f"  Ad: {path.name}", f"  Boyut: {_size(path.stat().st_size)}",
              f"  Süre: {_time(duration)} ({_num(duration)} sn)", f"  Biçim: {info['codec']}, {rate} Hz, "
              f"{'stereo' if info['channels'] > 1 else 'mono'}"
              + (f", {round(info['bitrate'] / 1000)} kbps" if info.get("bitrate") else "")]
    tag_names = {"title": "Parça adı", "artist": "Sanatçı", "album": "Albüm", "genre": "Tür", "date": "Yıl",
                 "year": "Yıl", "composer": "Besteci", "bpm": "BPM (etiket)", "tbpm": "BPM (etiket)", "comment": "Not"}
    tags = [f"  {label}: {info['tags'][key]}" for key, label in tag_names.items() if info["tags"].get(key)]
    lines += list(dict.fromkeys(tags))  # 3.45: tags are part of DOSYA (fixed section order, no ETİKETLER section)
    target_at = len(lines)  # 3.47: HEDEF KONTROLÜ goes here once the loudness is measured

    # Loudness
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    rms = float(np.sqrt(np.mean(mono ** 2))) if mono.size else 0.0
    clipped = int(np.sum(np.abs(samples) >= 0.999))
    try:
        import pyloudnorm

        lufs = pyloudnorm.Meter(rate).integrated_loudness(samples.T if samples.shape[0] > 1 else mono)
    except Exception as e:  # too short, or the package is missing
        log.debug("LUFS ölçülemedi: %s", e)
        lufs = None
    frame = rate // 2
    blocks = [float(np.sqrt(np.mean(mono[i:i + frame] ** 2))) for i in range(0, mono.size - frame + 1, frame)]
    loud_blocks = [_db(b) for b in blocks if b > 1e-4]
    dynamics = (np.percentile(loud_blocks, 95) - np.percentile(loud_blocks, 10)) if len(loud_blocks) > 4 else None
    lines += ["", "SES YÜKSEKLİĞİ"]
    if lufs is not None and math.isfinite(lufs):
        lines.append(f"  Algılanan yükseklik: {_num(lufs)} LUFS")
        facts["lufs"] = round(lufs, 1)
    try:
        tp = true_peak(samples)
    except Exception as e:
        log.debug("True peak ölçülemedi: %s", e)
        tp = None
    try:
        lra = loudness_range(samples, rate)
    except Exception as e:
        log.debug("LRA ölçülemedi: %s", e)
        lra = None
    # 3.44: sample peak and true peak are different measurements; both are shown, each with its own unit.
    # 3.48: values only here; every verdict is in HEDEF KONTROLÜ (the -1 dBTP hint contradicted the -3 dBTP rule).
    lines.append(f"  Örnek tepesi (sample peak): {_num(_db(peak))} dBFS")
    if tp is not None:
        lines.append(f"  Gerçek tepe (true peak, 4× örnekleme): {_num(_db(tp))} dBTP")
        facts["true_peak"] = round(_db(tp), 1)
    lines.append(f"  Ortalama (RMS): {_num(_db(rms))} dBFS")
    if lra is not None:
        lines.append(f"  Yükseklik aralığı (LRA, EBU R128): {_num(lra)} LU")
        facts["lra"] = round(lra, 1)
    if dynamics is not None:  # not a dynamics measure: kept only as information, without any verdict
        lines.append(f"  Bölüm yükseklik farkı (0,5 sn blokların %95−%10 RMS farkı; LRA değildir): {_num(dynamics)} dB")
    lines.append(f"  Kırpılan örnek: {clipped}")
    step("hedef")
    target, facts["warnings"] = target_check(info, rate, facts.get("lufs"), facts.get("true_peak"), facts.get("lra"),
                                             clipped)
    lines[target_at:target_at] = [""] + target

    # Silence at the edges
    threshold = 10 ** (-50 / 20)
    loud = np.flatnonzero(np.abs(mono) > threshold)
    if loud.size:
        head, tail = loud[0] / rate, (mono.size - loud[-1]) / rate
        lines.append(f"  Baştaki sessizlik: {_num(head, 2)} sn, sondaki sessizlik: {_num(tail, 2)} sn")

    # Stereo
    if samples.shape[0] > 1:
        left, right = samples[0], samples[1]
        corr = float(np.corrcoef(left, right)[0, 1]) if np.std(left) > 0 and np.std(right) > 0 else 1.0
        side = float(np.sqrt(np.mean(((left - right) / 2) ** 2)))
        width = side / max(rms, 1e-9)
        verdict = ("neredeyse mono" if corr > 0.97 else "dar" if width < 0.3 else "geniş" if width > 0.7 else "normal")
        lines += ["", "STEREO", f"  Sol-sağ benzerliği (korelasyon): {_num(corr, 2)}"
                  + (" — faz sorunu olabilir (mono'da ses kaybolur)" if corr < 0 else ""),
                  f"  Genişlik: {verdict}"]

    # Musical measurements on a mono copy
    y = librosa.resample(mono, orig_sr=rate, target_sr=ANALYSIS_RATE) if rate != ANALYSIS_RATE else mono
    tempo, beats = librosa.beat.beat_track(y=y, sr=ANALYSIS_RATE)
    tempo = float(np.atleast_1d(tempo)[0])
    chroma = librosa.feature.chroma_stft(y=y, sr=ANALYSIS_RATE).mean(axis=1)
    best = (-2.0, 0, "major")
    for shift in range(12):
        for mode, profile in (("major", MAJOR), ("minor", MINOR)):
            score = float(np.corrcoef(chroma, np.roll(profile, shift))[0, 1])
            if score > best[0]:
                best = (score, shift, mode)
    score, tonic, mode = best
    key_tr = f"{KEYS[tonic]} {'majör' if mode == 'major' else 'minör'}"
    key_en = f"{KEYS_EN[tonic]}{'' if mode == 'major' else 'm'}"
    centroid = float(librosa.feature.spectral_centroid(y=y, sr=ANALYSIS_RATE).mean())
    flatness = float(librosa.feature.spectral_flatness(y=y).mean())
    onset_rate = len(librosa.onset.onset_detect(y=y, sr=ANALYSIS_RATE)) / max(duration, 1)
    facts.update(tempo=round(tempo), key=key_tr, brightness=round(centroid), duration=round(duration), seconds=duration)
    step("BPM")
    bpm_lines, facts["bpm_warning"] = bpm_cross_check(tempo, y, ANALYSIS_RATE)
    lines += ["", "MÜZİKAL ÖZELLİKLER",
              f"  Tempo (Asiye, librosa beat_track): {_num(tempo)} BPM"
              + (f" (yarısı {round(tempo / 2)} / iki katı {round(tempo * 2)} de olabilir)" if tempo > 150 or tempo < 70
                 else ""),
              *bpm_lines,
              f"  Ton: {key_tr} ({key_en}) — güven: {'yüksek' if score > 0.75 else 'orta' if score > 0.55 else 'düşük'}",
              f"  Parlaklık (spektral merkez): {round(centroid)} Hz — "
              + ("parlak/tiz ağırlıklı" if centroid > 3000 else "koyu/bas ağırlıklı" if centroid < 1500 else "dengeli"),
              f"  Ses dokusu: {'gürültülü/perküsif' if flatness > 0.1 else 'tonal/melodik'} (düzlük {_num(flatness, 3)})",
              f"  Vuruş/olay yoğunluğu: saniyede {_num(onset_rate)}"]

    # Sections by loudness (10-second windows)
    window = 10
    step = int(window * rate)
    if mono.size > 3 * step:
        values = [_db(float(np.sqrt(np.mean(mono[i:i + step] ** 2)))) for i in range(0, mono.size - step // 2, step)]
        top = max(values)
        lines += ["", "BÖLÜMLER (10 saniyelik parçaların yüksekliği)"]
        for n, value in enumerate(values):
            bar = "█" * max(1, round(20 + (value - top)))  # 1 block = 1 dB below the loudest part
            lines.append(f"  {_time(n * window)}–{_time(min((n + 1) * window, duration))}  {bar} {_num(value)} dB")
        facts["loudest_at"] = _time(values.index(top) * window)
    return lines, facts


# Pictures

def picture_report(path: Path) -> tuple[list[str], str]:
    """(lines, base64 of a small copy for the model)."""
    import numpy as np
    from PIL import ExifTags, Image, ImageFilter, ImageStat

    lines = []
    with Image.open(path) as image:
        image.load()
        width, height = image.size
        gcd = math.gcd(width, height) or 1
        lines += ["DOSYA", f"  Ad: {path.name}", f"  Boyut: {_size(path.stat().st_size)}",
                  f"  Biçim: {image.format}, renk kipi {image.mode}" + (f", {getattr(image, 'n_frames', 1)} kare (hareketli)"
                                                                          if getattr(image, "n_frames", 1) > 1 else ""),
                  f"  Çözünürlük: {width} × {height} piksel ({_num(width * height / 1e6)} megapiksel), "
                  f"en-boy oranı {width // gcd}:{height // gcd}"]
        dpi = image.info.get("dpi")
        if dpi:
            lines.append(f"  DPI: {round(float(dpi[0]))}; baskıda {_num(width / max(float(dpi[0]), 1) * 2.54)} × "
                         f"{_num(height / max(float(dpi[1]), 1) * 2.54)} cm")
        if width == height:
            lines.append("  Kare: albüm kapağı oranına uygun" + (" (Spotify için en az 3000×3000 önerilir)"
                                                                  if width < 3000 else ""))
        exif = {}
        try:
            raw = image.getexif()
            exif = {ExifTags.TAGS.get(k, k): v for k, v in raw.items()}
            exif.update({ExifTags.TAGS.get(k, k): v for k, v in raw.get_ifd(0x8769).items()})
        except Exception:
            pass
        wanted = [("Make", "Üretici"), ("Model", "Cihaz"), ("LensModel", "Lens"), ("DateTimeOriginal", "Çekim tarihi"),
                  ("ExposureTime", "Pozlama"), ("FNumber", "Diyafram"), ("ISOSpeedRatings", "ISO"),
                  ("FocalLength", "Odak uzaklığı"), ("Software", "Yazılım")]
        exif_lines = []
        for key, label in wanted:
            value = exif.get(key)
            if value not in (None, ""):
                if key == "ExposureTime" and float(value) < 1:
                    value = f"1/{round(1 / float(value))} sn"
                elif key == "FNumber":
                    value = f"f/{_num(float(value))}"
                elif key == "FocalLength":
                    value = f"{_num(float(value), 0)} mm"
                exif_lines.append(f"  {label}: {str(value).strip()}")
        if exif_lines:
            lines += ["", "ÇEKİM BİLGİLERİ (EXIF)"] + exif_lines
        if "GPSInfo" in exif:
            lines.append("  ⚠️ Resimde konum (GPS) bilgisi var: paylaşmadan önce silmek isteyebilirsin.")

        rgb = image.convert("RGB")
        has_alpha = "A" in image.getbands()
        small = rgb.copy()
        small.thumbnail((400, 400))
        stat = ImageStat.Stat(small)
        hsv = np.asarray(small.convert("HSV"), dtype="float32")
        gray = small.convert("L")
        edges = np.asarray(gray.filter(ImageFilter.FIND_EDGES), dtype="float32")
        brightness = sum(stat.mean) / 3 / 255
        contrast = float(np.asarray(gray, dtype="float32").std()) / 255
        saturation = float(hsv[..., 1].mean()) / 255
        sharpness = float(edges.var())
        r, g, b = stat.mean
        lines += ["", "GÖRÜNÜM",
                  f"  Parlaklık: %{round(brightness * 100)} — " + ("karanlık" if brightness < 0.3 else "aydınlık"
                                                                     if brightness > 0.7 else "orta"),
                  f"  Kontrast: %{round(contrast * 100)} — " + ("düşük/soluk" if contrast < 0.15 else "yüksek"
                                                                  if contrast > 0.3 else "normal"),
                  f"  Doygunluk: %{round(saturation * 100)} — " + ("gri tonlarına yakın" if saturation < 0.15 else
                                                                     "canlı renkler" if saturation > 0.5 else "normal"),
                  f"  Keskinlik: {round(sharpness)} — " + ("bulanık olabilir" if sharpness < 100 else "net"),
                  f"  Renk sıcaklığı: " + ("sıcak (kırmızı/turuncu ağırlıklı)" if r > b + 12 else
                                           "soğuk (mavi ağırlıklı)" if b > r + 12 else "nötr"),
                  f"  Saydamlık: {'var' if has_alpha else 'yok'}"]
        palette = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
        counts = sorted(palette.getcolors(), reverse=True)
        colors = palette.getpalette()
        total = sum(c for c, _ in counts)
        lines += ["", "BASKIN RENKLER"]
        for count, index in counts[:6]:
            cr, cg, cb = colors[index * 3:index * 3 + 3]
            lines.append(f"  #{cr:02X}{cg:02X}{cb:02X}  %{round(count / total * 100)}  {_color_name(cr, cg, cb)}")

        preview = rgb.copy()
        preview.thumbnail((896, 896))
        buffer = io.BytesIO()
        preview.save(buffer, format="JPEG", quality=85)
    return lines, base64.b64encode(buffer.getvalue()).decode("ascii")


def _color_name(r: int, g: int, b: int) -> str:
    import colorsys

    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if l < 0.12:
        return "siyah"
    if l > 0.9:
        return "beyaz"
    if s < 0.15:
        return "gri"
    names = [(15, "kırmızı"), (40, "turuncu"), (65, "sarı"), (160, "yeşil"), (195, "turkuaz"), (250, "mavi"),
             (290, "mor"), (340, "pembe"), (360, "kırmızı")]
    degrees = h * 360
    name = next(n for limit, n in names if degrees < limit)
    return ("koyu " if l < 0.3 else "açık " if l > 0.7 else "") + name


# One file

async def analyze(path: Path, model: str, step=lambda name: None) -> str:
    """Write the report next to the file; returns a one-line summary for the chat. step(name): a stage starts (it may
    be called from a worker thread)."""
    kind = "music" if path.suffix.lower() in MUSIC else "picture"
    from starlette.concurrency import run_in_threadpool

    header = [f"Yerel Asistan analiz raporu — {datetime.now():%d.%m.%Y %H:%M}", "=" * 60, ""]
    if kind == "music":
        step("ölçüm")
        lines, facts = await run_in_threadpool(music_report, path, step)
        step("sözler")
        try:  # 3.49: SÖZLER is the last section (Asiye_Isterler.txt §3, §4); a failure here must not lose the report
            words, sung = await run_in_threadpool(lyrics.section, path, facts["seconds"], folder())
        except Exception as e:
            log.exception("Sözler çıkarılamadı: %s", path.name)
            words, sung = ["SÖZLER", lyrics.NOTE, f"  Sözler çıkarılamadı: {e}"], {}
        lines += [""] + words
        summary = (f"🎵 {path.name}: {_time(facts.get('duration', 0))}, {facts.get('tempo')} BPM, {facts.get('key')}"
                   + (", enstrümantal" if sung.get("instrumental") else
                      f", sözler: {lyrics.LANGUAGES.get(sung['language'], sung['language'])}" if sung.get("language")
                      else "")
                   + (f", {_num(facts['lufs'])} LUFS" if "lufs" in facts else "")
                   + (f" — hedef kontrolü: {facts['warnings']} uyarı" if facts.get("warnings") else " — hedefler tamam")
                   + (" — BPM'ler uyuşmuyor (raporda)" if facts.get("bpm_warning") else ""))
    else:
        step("ölçüm")
        lines, image = await run_in_threadpool(picture_report, path)
        step("yapay zekâ bakıyor")
        seen = await _ask(model, "Bu resmi Türkçe anlat: 1) Resimde ne var (kısa açıklama), 2) Atmosfer ve duygu, "
                          "3) Öne çıkan öğeler ve kompozisyon, 4) Resimdeki yazılar (varsa aynen), 5) Bir müzik parçasına "
                          "kapak olarak kullanılsa hangi tarz müziğe uyar. Kısa maddelerle yaz, görmediğin şeyi uydurma.",
                          image)
        if seen:
            lines += ["", "YAPAY ZEKÂNIN GÖRDÜKLERİ"] + ["  " + c for c in seen.splitlines()]
        first = next((c.strip(" -*0123456789.)") for c in (seen or "").splitlines() if len(c.strip()) > 20), "")
        summary = f"🖼️ {path.name}: " + (first[:120] if first else lines[4].strip())
    report = report_path(path)
    # 3.45: UTF-8 without BOM and LF line ends (Asiye_Isterler.txt §7; today's Notepad reads both right)
    report.write_text("\n".join(header + lines) + "\n", encoding="utf-8", newline="\n")
    log.info("Analiz yazıldı: %s", report.name)
    return summary


async def _ask(model: str, prompt: str, image: str | None = None) -> str:
    message = {"role": "user", "content": prompt}
    if image:
        message["images"] = [image]
    try:
        text, reason = await llm.chat_text_full(model, [message], num_predict=1500)
    except llm.OllamaError as e:
        log.warning("Analiz yorumu alınamadı: %s", e)
        return ""
    if reason == "length":  # 3.44: still cut off: end at the last complete sentence instead of mid-word
        log.warning("Analiz yorumu uzunluk sınırında kesildi")
        cut = max(text.rfind(". "), text.rfind(".\n"), text.rfind("\n"))
        text = (text[:cut + 1].rstrip() if cut > len(text) // 2 else text.rstrip()) + "\n(yorum burada kısaltıldı)"
    return text


# Chat

def open_reply(text: str) -> str | None:
    """"Analiz klasörünü aç": opens the folder in Explorer."""
    if not wants_open(text):
        return None
    where = folder()
    try:
        os.startfile(str(where))  # Windows only
        return f"📂 Klasörü açtım: {where}"
    except (AttributeError, OSError):
        return f"📂 Analiz klasörü: {where}"


async def run(text: str, model: str):
    """Analyze the waiting files; yields ("progress", text) while working and ("text", reply) at the end."""
    low = text.replace("I", "ı").replace("İ", "i").lower()
    files = waiting_files(again=bool(_AGAIN.search(low)))
    where = folder()
    if not files:
        yield "text", (f"Klasörde analiz edilecek yeni dosya yok (📂 {where}). Müzik (mp3, wav, flac, m4a…) ya da resim "
                       "(jpg, png, webp…) at, sonra tekrar söyle. Daha önce analiz edilmişleri baştan yapmak için: "
                       "\"hepsini yeniden analiz et\".")
        return
    done, failed = [], []
    loop = asyncio.get_running_loop()
    for number, path in enumerate(files, 1):
        # 3.51 (Asiye_Isterler.txt §2): one command does every stage in order, and the screen shows each one as it
        # starts: "🔎 1/1 Palabras de Sal 2: ölçüm… hedef… BPM… sözler…"
        stages, news = [], asyncio.Queue()
        yield "progress", f"🔎 {number}/{len(files)} {path.stem}: başlıyor…"
        work = asyncio.ensure_future(analyze(path, model, lambda name: loop.call_soon_threadsafe(news.put_nowait, name)))
        while True:
            wait = asyncio.ensure_future(news.get())
            await asyncio.wait({work, wait}, return_when=asyncio.FIRST_COMPLETED)
            if not wait.done():
                wait.cancel()
            names = [wait.result()] if wait.done() and not wait.cancelled() else []
            while not news.empty():
                names.append(news.get_nowait())
            if names:
                stages += names
                yield "progress", f"🔎 {number}/{len(files)} {path.stem}: " + " ".join(f"{s}…" for s in stages)
            if work.done():
                break
        try:
            done.append(work.result())
        except Exception as e:
            log.exception("Analiz edilemedi: %s", path.name)
            failed.append(f"⚠️ {path.name}: {e}")
    lines = [f"✅ {len(done)} dosya analiz edildi. Raporlar aynı klasörde, her dosyanın yanında \"…{REPORT_SUFFIX}\" olarak:"]
    lines += [f"- {s}" for s in done] + [f"- {f}" for f in failed]
    lines.append(f"\n📂 {where}")
    yield "text", "\n".join(lines)
