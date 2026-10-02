"""Lyrics (3.49, Asiye_Isterler.txt §4): a draft transcript of the sung words at the end of the music report.

Not rewritten: HourGlow's own pipeline Scripts\\analiz\\analiz.py is loaded from Drive each time (like hg_bpm.py) and its
functions do the work: separate_vocals (Demucs two stems, run with this Python), transcribe (openai-whisper on the GPU;
language=None → Whisper detects it), flatten_words, is_adlib_segment, find_gaps (no-lyric spans of at least
DEFAULT_GAP_THRESHOLD seconds; ad-libs are not lyrics). Rules from HourGlow's 03.08.2026 test: Demucs is required
(Whisper hallucinates on the full mix) and the model is medium (large on this GPU gives "Thank you" ×7).
The stems go to a temporary folder and are deleted (never written into Drive).

3.50: all of it runs in a child process (`python -m app.lyrics`, same Python), never inside the assistant. stt.py
loads the cuDNN of the pip nvidia-cudnn-cu12 package for faster-whisper (and puts its folder on PATH); torch's own
cudnn_cnn64_9.dll then failed in the same process: "[WinError 127] … cudnn_cnn64_9.dll". The child gets a PATH
without those nvidia folders, so torch (and Demucs, its grandchild) load only torch's own DLLs.
"""

import gc
import importlib.util
import json
import logging
import os
import shutil
import subprocess
import sys
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


RESULT_MARK = "@@SOZLER@@"  # the child's answer line; everything else it prints (Demucs, Whisper progress) is noise
TIMEOUT = 30 * 60
ROOT = Path(__file__).resolve().parent.parent


def _child_env() -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    nvidia = os.sep + "site-packages" + os.sep + "nvidia" + os.sep
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                  if p and nvidia not in os.path.normcase(os.path.normpath(p)) + os.sep)
    return env


def section(path: Path, duration: float, folder: Path | None) -> tuple[list[str], dict]:
    """SÖZLER report lines + {"language": "es" | None, "instrumental": bool}, from a child process (see above)."""
    args = json.dumps({"path": str(path), "duration": duration, "folder": str(folder) if folder else None})
    done = subprocess.run([sys.executable, "-m", "app.lyrics", args], cwd=ROOT, env=_child_env(), capture_output=True,
                          timeout=TIMEOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    out = done.stdout.decode("utf-8", "replace")
    answer = next((line[len(RESULT_MARK):] for line in reversed(out.splitlines()) if line.startswith(RESULT_MARK)), None)
    if answer is None:
        tail = done.stderr.decode("utf-8", "replace").strip().splitlines()[-15:]
        log.warning("Söz çıkarma alt süreci sonuç vermedi (çıkış %s):\n%s", done.returncode, "\n".join(tail))
        raise RuntimeError(next((t for t in reversed(tail) if t.strip()), f"alt süreç çıkış kodu {done.returncode}"))
    result = json.loads(answer)
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result["lines"], result["info"]


# Suno lyrics (3.52, Asiye_Isterler.txt §9): the text comes from "<song>.suno.txt", only the times from Whisper.
# Suno's lines are aligned IN ORDER with Whisper's words (a global alignment, like comparing two texts), so a repeated
# chorus takes the next sung chorus, never the first one again. A line that does not line up gets "?:??", not a guess.

SAME_WORD = 0.8   # word similarity (difflib, accents and punctuation removed) for a sure match
NEAR_WORD = 0.6   # still the same word heard a bit wrong ("Besame" / "Desame")
GAP = -1.0        # a Suno word not heard, or a Whisper word not in Suno (ad-libs, hallucinations)


def suno_path(path: Path) -> Path:
    """"Song.wav" → "Song.suno.txt" next to it."""
    return path.with_name(path.stem + ".suno.txt")


def read_suno(path: Path) -> list[tuple[str | None, str]]:
    """[(section or None, line)]: "[Verse 1]" lines name the section of the lines after them; empty lines are skipped."""
    section, found = None, []
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        text = raw.strip()
        if not text:
            continue
        if text.startswith("[") and text.endswith("]"):
            section = text[1:-1].strip()
            continue
        found.append((section, text))
    return found


def _fold(text: str, hg) -> str:
    import unicodedata

    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return hg.normalize(plain.replace("’", "'"))  # analiz.py's normalize: lower case, a-z 0-9 ' only


def whisper_words(result: dict, hg) -> list[dict]:
    """[{"word": as heard, "key": folded, "start": s}] in sung order."""
    words = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            for key in _fold(w.get("word", ""), hg).split():
                words.append({"word": w["word"].strip(), "key": key, "start": float(w["start"])})
    return words


def _similar(a: str, b: str) -> float:
    import difflib

    return 1.0 if a == b else difflib.SequenceMatcher(None, a, b).ratio()


def align(left: list[str], right: list[str]) -> list[tuple[int | None, int | None, float]]:
    """Order-keeping alignment of two word lists (Needleman-Wunsch): [(i, j, similarity)], None on the side of a gap."""
    n, m = len(left), len(right)
    sim = [[_similar(a, b) for b in right] for a in left]

    def gain(s: float) -> float:
        return 2.0 if s >= SAME_WORD else 1.0 if s >= NEAR_WORD else -1.0

    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = i * GAP
    for j in range(1, m + 1):
        score[0][j] = j * GAP
    for i in range(1, n + 1):
        row, above = score[i], score[i - 1]
        for j in range(1, m + 1):
            row[j] = max(above[j - 1] + gain(sim[i - 1][j - 1]), above[j] + GAP, row[j - 1] + GAP)
    pairs, i, j = [], n, m
    while i or j:
        if i and j and score[i][j] == score[i - 1][j - 1] + gain(sim[i - 1][j - 1]):
            pairs.append((i - 1, j - 1, sim[i - 1][j - 1]))
            i, j = i - 1, j - 1
        elif i and score[i][j] == score[i - 1][j] + GAP:
            pairs.append((i - 1, None, 0.0))
            i -= 1
        else:
            pairs.append((None, j - 1, 0.0))
            j -= 1
    return pairs[::-1]


def suno_lines(suno: list[tuple[str | None, str]], heard: list[dict], hg) -> tuple[list[str], str]:
    """SÖZLER body for a Suno text: section headers, "m:ss  line" (or "?:??"), and the sung/written differences.
    Returns (lines, "timed/total")."""
    keys, owner = [], []  # every Suno word with the number of its line
    for number, (_, text) in enumerate(suno):
        for key in _fold(text, hg).split():
            keys.append(key)
            owner.append(number)
    per_line = [[] for _ in suno]  # [(Suno word index, Whisper word index or None, similarity)]
    extra = []                    # Whisper words between Suno words (not in the text)
    for i, j, s in align(keys, [w["key"] for w in heard]):
        if i is None:
            extra.append(j)
        else:
            per_line[owner[i]].append((i, j, s))
    times, differences = [], []
    for number, (_, text) in enumerate(suno):
        pairs = per_line[number]
        sure = sum(1 for _, j, s in pairs if j is not None and s >= NEAR_WORD)
        heard_at = [j for _, j, _ in pairs if j is not None]
        if not pairs or sure < max(1, (len(pairs) + 1) // 2):
            times.append(None)
            continue
        times.append(heard[heard_at[0]]["start"])
        span = range(heard_at[0], heard_at[-1] + 1)
        inserted = [j for j in extra if j in span and heard[j]["key"] not in hg.ADLIB_TOKENS]
        if inserted or any(j is None or heard[j]["key"] != keys[i] for i, j, _ in pairs):
            differences.append((times[-1], text, " ".join(heard[j]["word"] for j in span)))
    timed = sum(1 for t in times if t is not None)
    lines = [f"  Eşleşme: {timed}/{len(suno)} dize zamanlandı" + ("" if timed == len(suno) else
                                                                   " (\"?:??\" = Whisper'da bulunamadı, zaman uydurulmadı)")]
    current = object()
    for (part, text), start in zip(suno, times):
        if part != current:
            lines += ["", f"  [{part}]"] if part else [""]
            current = part
        lines.append(f"  {_time(start) if start is not None else '?:??'}  {text}")
    lines += ["", "  SÖYLENEN / YAZILAN FARKLARI (bilgi: ya Whisper hatası ya da Suno şarkıda sözü değiştirmiş)"]
    lines += [f"    {_time(t)}  Suno: \"{text}\"   Whisper: \"{said}\"" for t, text, said in differences] or ["    yok"]
    return lines, f"{timed}/{len(suno)}"


def _section(path: Path, duration: float, folder: Path | None) -> tuple[list[str], dict]:
    """The work itself; runs only in the child process."""
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
    kept = {"segments": [s for s, _ in segments]}
    language = (f"  Dil: {LANGUAGES.get(code, code or 'bilinmiyor')} ({code}, Whisper algıladı; şarkının başına bakar, "
                "karışık dilli şarkıda diğer dil yanlış yazılabilir)")
    suno = suno_path(path)
    if suno.is_file():  # 3.52 (§9): Suno's official text, Whisper's times
        lines = ["SÖZLER", "  Kaynak: Suno metni (resmi); zamanlar Whisper'dan", language]
        body, info["suno"] = suno_lines(read_suno(suno), whisper_words(kept, hg), hg)
        lines += body
    else:
        lines += [language, f"  Model: whisper-{MODEL}, izole vokal (Demucs)", ""]
        for seg, text in segments:
            lines.append(f"  {_time(seg['start'])}  {text}" + ("  [ad-lib]" if hg.is_adlib_segment(seg) else ""))

    gaps, adlibs = hg.find_gaps(kept, hg.flatten_words(kept), hg.DEFAULT_GAP_THRESHOLD, duration)
    lines += ["", f"  Vokalsiz aralıklar (≥ {hg.DEFAULT_GAP_THRESHOLD:.0f} sn; ad-lib söz sayılmaz):"]
    if not gaps:
        lines.append("  yok")
    for start, end, length in gaps:
        lines.append(f"  {_time(start)} – {_time(end)}  ({round(length)} sn)")
        for a_start, a_end in hg.adlibs_in_gap(start, end, adlibs):
            lines.append(f"      ad-lib: {_time(a_start)} – {_time(a_end)}")
    return lines, info


if __name__ == "__main__":  # python -m app.lyrics '{"path": …, "duration": …, "folder": …}'
    logging.basicConfig(level=logging.INFO)
    job = json.loads(sys.argv[1])
    try:
        found, about = _section(Path(job["path"]), job["duration"], Path(job["folder"]) if job["folder"] else None)
        reply = {"lines": found, "info": about}
    except Exception as e:
        log.exception("Sözler çıkarılamadı")
        reply = {"error": str(e)}
    sys.stdout.flush()
    print(RESULT_MARK + json.dumps(reply, ensure_ascii=False), flush=True)
