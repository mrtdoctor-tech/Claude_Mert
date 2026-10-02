"""Folder analysis (3.26): music and pictures dropped into the "Asiye" folder of HourGlow Music.

"Asiye klasöründeki dosyaları analiz et" in the chat: every music and picture file in the folder that has no report
yet (or changed since) is analyzed, and the result is written next to it as "<file>.analiz.txt". Everything runs on
this computer: the measurements with librosa / pyloudnorm / Pillow, the picture description with the local model
(gemma3 can see pictures). Only people recognized by voice or passcode can use it (the folder is theirs), not guests.

Music: length, format, tags, loudness (LUFS, peak, RMS, dynamics, clipping), tempo (BPM), key, brightness, stereo
width, silence at the start/end, sections by loudness. 3.45: no model comment on music (it called -1.6 dBTP "safe" and
suggested compression for more dynamics); the report is measurements only, in a fixed order (Asiye_Isterler.txt §3).
Pictures: size, format, EXIF (camera, date, settings), brightness, contrast, saturation, sharpness, dominant colors,
warm/cool, and what the model sees in it (description, mood, text in the picture).
"""

import base64
import io
import logging
import math
import os
import re
from datetime import datetime
from pathlib import Path

from . import config, identity, llm

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


def music_report(path: Path) -> tuple[list[str], dict]:
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
        advice = ("Spotify/YouTube (-14 LUFS) için yüksek; platform kısacaktır" if lufs > -12 else
                  "yayın platformları için uygun seviyede (-14 LUFS civarı)" if lufs >= -16 else
                  "yayın platformları için kısık; mastering'de yükseltilebilir")
        lines.append(f"  Algılanan yükseklik: {_num(lufs)} LUFS ({advice})")
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
    # 3.44: sample peak and true peak are different measurements; both are shown, each with its own unit
    lines.append(f"  Örnek tepesi (sample peak): {_num(_db(peak))} dBFS" + (" — kırpılma sınırında" if peak >= 0.999 else ""))
    if tp is not None:
        lines.append(f"  Gerçek tepe (true peak, 4× örnekleme): {_num(_db(tp))} dBTP"
                     + (" — 0 dBTP üstü: dönüştürmede (mp3/AAC) bozulma olabilir" if tp > 1.0
                        else " — yayın platformlarının önerdiği -1 dBTP'nin üstünde" if _db(tp) > -1 else ""))
        facts["true_peak"] = round(_db(tp), 1)
    lines.append(f"  Ortalama (RMS): {_num(_db(rms))} dBFS")
    if lra is not None:
        lines.append(f"  Yükseklik aralığı (LRA, EBU R128): {_num(lra)} LU")
        facts["lra"] = round(lra, 1)
    if dynamics is not None:  # not a dynamics measure: kept only as information, without any verdict
        lines.append(f"  Bölüm yükseklik farkı (0,5 sn blokların %95−%10 RMS farkı; LRA değildir): {_num(dynamics)} dB")
    lines.append(f"  Kırpılan örnek: {clipped}" + (" (bozulma duyulabilir)" if clipped > rate // 100 else ""))

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
    facts.update(tempo=round(tempo), key=key_tr, brightness=round(centroid), duration=round(duration))
    lines += ["", "MÜZİKAL ÖZELLİKLER",
              f"  Tempo: {round(tempo)} BPM" + (f" (yarısı {round(tempo / 2)} / iki katı {round(tempo * 2)} de olabilir)"
                                                 if tempo > 150 or tempo < 70 else ""),
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

async def analyze(path: Path, model: str) -> str:
    """Write the report next to the file; returns a one-line summary for the chat."""
    kind = "music" if path.suffix.lower() in MUSIC else "picture"
    from starlette.concurrency import run_in_threadpool

    header = [f"Yerel Asistan analiz raporu — {datetime.now():%d.%m.%Y %H:%M}", "=" * 60, ""]
    if kind == "music":
        lines, facts = await run_in_threadpool(music_report, path)
        summary = (f"🎵 {path.name}: {_time(facts.get('duration', 0))}, {facts.get('tempo')} BPM, {facts.get('key')}"
                   + (f", {_num(facts['lufs'])} LUFS" if "lufs" in facts else ""))
    else:
        lines, image = await run_in_threadpool(picture_report, path)
        seen = await _ask(model, "Bu resmi Türkçe anlat: 1) Resimde ne var (kısa açıklama), 2) Atmosfer ve duygu, "
                          "3) Öne çıkan öğeler ve kompozisyon, 4) Resimdeki yazılar (varsa aynen), 5) Bir müzik parçasına "
                          "kapak olarak kullanılsa hangi tarz müziğe uyar. Kısa maddelerle yaz, görmediğin şeyi uydurma.",
                          image)
        if seen:
            lines += ["", "YAPAY ZEKÂNIN GÖRDÜKLERİ"] + ["  " + c for c in seen.splitlines()]
        first = next((c.strip(" -*0123456789.)") for c in (seen or "").splitlines() if len(c.strip()) > 20), "")
        summary = f"🖼️ {path.name}: " + (first[:120] if first else lines[4].strip())
    report = report_path(path)
    report.write_text("\n".join(header + lines) + "\n", encoding="utf-8-sig")  # BOM: Notepad shows ç/ş right
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
    for number, path in enumerate(files, 1):
        yield "progress", f"🔎 {number}/{len(files)}: {path.name} analiz ediliyor…"
        try:
            done.append(await analyze(path, model))
        except Exception as e:
            log.exception("Analiz edilemedi: %s", path.name)
            failed.append(f"⚠️ {path.name}: {e}")
    lines = [f"✅ {len(done)} dosya analiz edildi. Raporlar aynı klasörde, her dosyanın yanında \"…{REPORT_SUFFIX}\" olarak:"]
    lines += [f"- {s}" for s in done] + [f"- {f}" for f in failed]
    lines.append(f"\n📂 {where}")
    yield "text", "\n".join(lines)
