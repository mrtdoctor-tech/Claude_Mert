"""Inventory of the HourGlow Music scripts (3.33): "Betiklerimi incele".

The user wants to know which of the HourGlow scripts the assistant's own folder analysis (analysis.py) already covers,
so that some conda environments can be dropped. Nobody here has seen those scripts, so this lists them instead of
guessing: for every .py / .ipynb / .bat under HourGlowMusic\\Scripts (the parent of the "Asiye" folder) its size, date,
first comment line, the libraries it imports (read with `ast`, never run) and, for .bat files, the conda environment and
scripts it starts. The list is written to Asiye\\betik_envanteri.txt and summarized in the chat.
"""

import ast
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import analysis

REPORT_NAME = "betik_envanteri.txt"
SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "env", "node_modules", "site-packages", ".ipynb_checkpoints"}
MAX_FILES = 400
_COMMAND = re.compile(r"\b(betik|script|skript)\w*\b.*\b(incele|tara|listele|envanter|özetle|analiz)\w*"
                      r"|\b(envanter|incele|tara)\w*\b.*\b(betik|script|skript)\w*")
# What the assistant's own analysis (analysis.py) does, by library the scripts might use for the same job
COVERED = {"librosa": "tempo, ton, parlaklık", "pyloudnorm": "LUFS", "soundfile": "ses okuma", "av": "ses okuma",
           "pydub": "ses okuma/süre", "mutagen": "etiketler", "pil": "resim bilgileri, renkler", "pillow": "resim",
           "numpy": "hesaplama", "scipy": "hesaplama", "wave": "ses okuma", "audioread": "ses okuma", "exifread": "EXIF"}
STANDARD = {"os", "sys", "re", "json", "time", "datetime", "pathlib", "glob", "shutil", "subprocess", "math", "random",
            "csv", "argparse", "logging", "collections", "itertools", "functools", "typing", "io", "string", "tempfile",
            "threading", "traceback", "hashlib", "base64", "uuid", "urllib", "copy", "dataclasses", "enum", "textwrap",
            "zipfile", "platform", "statistics", "warnings", "concurrent", "asyncio", "queue", "struct", "pprint",
            "__future__", "abc", "contextlib", "fnmatch", "unicodedata", "locale", "calendar", "signal", "socket",
            "http", "email", "html", "xml", "sqlite3", "pickle", "configparser", "getpass", "shlex", "wave", "codecs"}


STANDARD |= set(getattr(sys, "stdlib_module_names", ()))  # 3.34: difflib, gc, importlib were counted as packages

# 3.44: which conda environment each script runs in, as the user reported it (the .py files themselves don't say).
# muzik got opencv-python-headless==4.11.0.86: hg_olcum / hg_dikis give the same output there as in the ComfyUI env.
KNOWN_ENVS = {name: "muzik" for name in (
    "hg_olcum", "hg_dikis", "hg_bpm", "hg_ses_kalite", "hg_qc", "muzik_analiz", "fvts", "analiz",
    "suno_katalog_cek", "suno_koken_zinciri", "suno_koken_zinciri_v2", "test_qc")}
KNOWN_ENVS["txt2speech_tr"] = "tts"  # Coqui XTTS; its scripts live outside Scripts (W:\\Derlemeler, per the HourGlow notes)
_COPY_SUFFIX = re.compile(r"(?:\s*-\s*(?:copy|kopya)|\s*\(\d+\)|-\d+)$", re.I)  # "hg_qc-1", "analiz (2)", "x - Copy"
ANACONDA_ACTIVATE = r"call C:\Apps\anaconda3\Scripts\activate.bat"


def known_env(path: Path) -> str | None:
    return KNOWN_ENVS.get(_COPY_SUFFIX.sub("", path.stem).lower())


def _bare_conda(text: str) -> bool:
    """A .bat that says just "conda activate X": on this computer PATH's conda is Pinokio's (P:\\pinokio\\bin\\miniconda),
    which doesn't know the Anaconda environments in C:\\Apps\\anaconda3\\envs."""
    return any(re.search(r"\bconda(?:\.bat|\.exe)?\s+activate\b", line, re.I) and "anaconda3" not in line.lower()
               for line in text.splitlines() if not _COMMENT.match(line))


def is_command(text: str) -> bool:
    low = text.replace("I", "ı").replace("İ", "i").lower()
    return len(low) <= 120 and bool(_COMMAND.search(low))


def scripts_folder() -> Path | None:
    where = analysis.folder()
    return where.parent if where else None


def _imports(source: str) -> tuple[set[str], str]:
    """(top-level modules, first comment/docstring line)."""
    modules, note = set(), ""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                modules.add(node.module.split(".")[0])
        doc = ast.get_docstring(tree)
        if doc:
            note = doc.strip().splitlines()[0]
    else:  # still show what it seems to use
        modules |= set(re.findall(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", source, re.M))
    if not note:
        comment = next((l.strip("# ").strip() for l in source.splitlines()
                        if l.strip().startswith("#") and not l.startswith("#!") and len(l.strip()) > 3), "")
        note = comment
    return modules, note[:140]


def _notebook(path: Path) -> str:
    try:
        cells = json.loads(path.read_text(encoding="utf-8", errors="replace")).get("cells", [])
    except ValueError:
        return ""
    return "\n".join("".join(c.get("source", [])) for c in cells if c.get("cell_type") == "code")


_ENV_PATTERNS = [
    r"\bconda(?:\.exe|\.bat)?\s+activate\s+([\w.-]+)",      # conda activate muzik
    r"\bactivate(?:\.bat)?\s+([\w.-]+)",                      # call ...\activate.bat ai_assistant
    r"\bconda(?:\.exe|\.bat)?\s+(?:run|create|env\s+\w+|install)\b[^\n]*?(?:-n|--name)\s+([\w.-]+)",
    r"envs[\\/]+([\w.-]+)[\\/]",                               # C:\Apps\anaconda3\envs\muzik\python.exe
]
_COMMENT = re.compile(r"^\s*(?:rem\b|::|#|echo\b|write-host\b|@?echo\b)", re.I)


def _batch(text: str) -> tuple[set[str], list[str]]:
    """(conda environments it uses, .py files it starts), ignoring comments and printed messages."""
    envs, started = set(), set()
    for line in text.splitlines():
        if _COMMENT.match(line):
            continue
        for pattern in _ENV_PATTERNS:
            envs |= {e for e in re.findall(pattern, line, re.I) if not e.startswith(("-", "%", "$"))}
        started |= {Path((a or b).replace("%~dp0", "")).name for a, b in re.findall(r'"([^"]+\.py)"|([\w.()\\/%~-]+\.py)\b', line)}
    envs -= {"activate", "deactivate"}
    return envs, sorted(started)


def build() -> tuple[str, str]:
    """(chat summary, report path) — writes the inventory into the Asiye folder."""
    root = scripts_folder()
    if not root or not root.is_dir():
        return "HourGlow Scripts klasörünü bulamadım (Asiye klasörünün bir üstü olmalı).", ""
    rows, libs, env_use, py_envs, bare, count = [], Counter(), Counter(), Counter(), [], 0
    for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
        if count >= MAX_FILES:
            break
        if not path.is_file() or any(part.lower() in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        kind = path.suffix.lower()
        if kind not in (".py", ".ipynb", ".bat", ".cmd", ".ps1"):
            continue
        count += 1
        rel = path.relative_to(root)
        stat = path.stat()
        head = f"{rel}  ({stat.st_size / 1024:.0f} KB, {datetime.fromtimestamp(stat.st_mtime):%d.%m.%Y})"
        text = path.read_text(encoding="utf-8", errors="replace")
        if kind in (".py", ".ipynb"):
            modules, note = _imports(_notebook(path) if kind == ".ipynb" else text)
            outside = sorted(m for m in modules if m.lower() not in STANDARD)
            local = {p.stem for p in root.rglob("*.py")}
            outside = [m for m in outside if m not in local]  # their own helper files are not libraries
            libs.update(m.lower() for m in outside)
            env = known_env(path)
            if env:
                py_envs[env] += 1
            rows.append(f"{head}\n    Ne yapıyor (ilk not): {note or '-'}\n    Kullandığı paketler: {', '.join(outside) or '-'}"
                        f"\n    Ortam: {env + ' (kullanıcının bildirdiği)' if env else 'bilinmiyor'}")
        else:
            envs, started = _batch(text)
            env_use.update(envs)
            warn = ""
            if kind in (".bat", ".cmd") and _bare_conda(text):
                bare.append(str(rel))
                warn = (f"\n    ⚠️ 'conda activate' PATH'teki conda'yı (Pinokio) kullanır, Anaconda ortamlarını bulamaz."
                        f" Şöyle olmalı: {ANACONDA_ACTIVATE} {next(iter(sorted(envs)), '<ortam>')}")
            rows.append(f"{head}\n    Ortam: {', '.join(sorted(envs)) or '-'}\n    Çalıştırdığı betikler: {', '.join(started) or '-'}"
                        + warn)
    covered = [f"{lib} ({COVERED[lib]})" for lib in sorted(libs) if lib in COVERED]
    missing = [f"{lib} ({n} betikte)" for lib, n in libs.most_common() if lib not in COVERED]
    lines = [f"HourGlow betik envanteri — {datetime.now():%d.%m.%Y %H:%M}", f"Klasör: {root}", "=" * 70, "",
             f"Betik sayısı: {count}", "",
             "Asistanın kendi analizinin de yaptığı işlere ait paketler:", "  " + (", ".join(covered) or "-"), "",
             "Asistanın YAPMADIĞI işlere ait paketler (bunlar için ortamlar gerekli):", "  " + (", ".join(missing) or "-"),
             "", "Başlatma dosyalarında geçen conda ortamları: " + (", ".join(f"{e} ({n})" for e, n in env_use.most_common())
                                                               or "-"),
             "Python betiklerinin ortamları (kullanıcının bildirdiği): " + (", ".join(f"{e} ({n})" for e, n in py_envs.most_common())
                                                                          or "-"),
             "TTS (tts ortamı) betikleri bu klasörde yok; notlara göre W:\\Derlemeler altında (txt2speech_tr.py).",
             ] + ([f"⚠️ Düz 'conda activate' kullanan başlatma dosyaları ({ANACONDA_ACTIVATE} <ortam> olmalı): "
                   + ", ".join(bare)] if bare else []) + ["", "=" * 70, ""] + rows
    report = analysis.folder() / REPORT_NAME
    report.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    summary = [f"📋 {count} betik inceledim (çalıştırmadan, yalnızca okudum). Rapor: 📂 {report}",
               f"- Asistanın analizinin de kapsadığı paketler: {', '.join(covered) or 'yok'}",
               f"- Asistanın **kapsamadığı** paketler: {', '.join(missing[:15]) or 'yok'}"
               + (" …" if len(missing) > 15 else ""),
               f"- Başlatma dosyalarındaki ortamlar: {', '.join(env_use) or 'bulunamadı'}",
               f"- Python betiklerinin ortamları: {', '.join(f'{e} ({n})' for e, n in py_envs.most_common()) or 'bilinmiyor'}",
               *([f"- ⚠️ Düz 'conda activate' kullanan: {', '.join(bare)} → `{ANACONDA_ACTIVATE} <ortam>` olmalı"] if bare else []),
               "Bu raporu Claude'a gönderirsen hangi ortamların gerçekten gerekli olduğunu birlikte çıkarırız."]
    return "\n".join(summary), str(report)
