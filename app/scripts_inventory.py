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


def _batch(text: str) -> tuple[set[str], list[str]]:
    envs = set(re.findall(r"(?:conda|activate)(?:\.bat)?\s+(?:activate\s+)?([\w.-]+)", text, re.I))
    envs |= set(re.findall(r"envs[\\/]+([\w.-]+)", text, re.I))
    envs -= {"activate", "deactivate", "run", "call"}
    started = [a or b for a, b in re.findall(r'"([^"]+\.py)"|([\w.()\\/-]+\.py)\b', text)]
    return envs, sorted({Path(s.strip()).name for s in started})


def build() -> tuple[str, str]:
    """(chat summary, report path) — writes the inventory into the Asiye folder."""
    root = scripts_folder()
    if not root or not root.is_dir():
        return "HourGlow Scripts klasörünü bulamadım (Asiye klasörünün bir üstü olmalı).", ""
    rows, libs, env_use, count = [], Counter(), Counter(), 0
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
            rows.append(f"{head}\n    Ne yapıyor (ilk not): {note or '-'}\n    Kullandığı paketler: {', '.join(outside) or '-'}")
        else:
            envs, started = _batch(text)
            env_use.update(envs)
            rows.append(f"{head}\n    Ortam: {', '.join(sorted(envs)) or '-'}\n    Çalıştırdığı betikler: {', '.join(started) or '-'}")
    covered = [f"{lib} ({COVERED[lib]})" for lib in sorted(libs) if lib in COVERED]
    missing = [f"{lib} ({n} betikte)" for lib, n in libs.most_common() if lib not in COVERED]
    lines = [f"HourGlow betik envanteri — {datetime.now():%d.%m.%Y %H:%M}", f"Klasör: {root}", "=" * 70, "",
             f"Betik sayısı: {count}", "",
             "Asistanın kendi analizinin de yaptığı işlere ait paketler:", "  " + (", ".join(covered) or "-"), "",
             "Asistanın YAPMADIĞI işlere ait paketler (bunlar için ortamlar gerekli):", "  " + (", ".join(missing) or "-"),
             "", "Başlatma dosyalarında geçen conda ortamları: " + (", ".join(f"{e} ({n})" for e, n in env_use.most_common())
                                                               or "-"), "", "=" * 70, ""] + rows
    report = analysis.folder() / REPORT_NAME
    report.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    summary = [f"📋 {count} betik inceledim (çalıştırmadan, yalnızca okudum). Rapor: 📂 {report}",
               f"- Asistanın analizinin de kapsadığı paketler: {', '.join(covered) or 'yok'}",
               f"- Asistanın **kapsamadığı** paketler: {', '.join(missing[:15]) or 'yok'}"
               + (" …" if len(missing) > 15 else ""),
               f"- Başlatma dosyalarındaki ortamlar: {', '.join(env_use) or 'bulunamadı'}",
               "Bu raporu Claude'a gönderirsen hangi ortamların gerçekten gerekli olduğunu birlikte çıkarırız."]
    return "\n".join(summary), str(report)
