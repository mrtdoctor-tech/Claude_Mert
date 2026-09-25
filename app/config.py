"""Paths and user settings. Everything is stored under the local data folder."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("ASISTAN_DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "asistan.db"
SETTINGS_PATH = DATA_DIR / "settings.json"

DEFAULTS = {
    "assistant_name": "Asistan",
    "model": "gemma3:4b",
    "whisper_model": "small",
    "language": "tr",
}


def load() -> dict:
    settings = dict(DEFAULTS)
    if SETTINGS_PATH.exists():
        try:
            settings.update(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return settings


def save(changes: dict) -> dict:
    settings = load()
    settings.update({k: v for k, v in changes.items() if k in DEFAULTS and v is not None})
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings
