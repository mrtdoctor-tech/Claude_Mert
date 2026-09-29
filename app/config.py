"""Paths and user settings.

The data folder (conversations, memories) may be shared between computers through OneDrive.
Settings are per computer (a slow laptop and a desktop want different models), so they live in
%LOCALAPPDATA%\YerelAsistan on Windows.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("ASISTAN_DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "asistan.db"
_local = os.environ.get("ASISTAN_SETTINGS_DIR") or (
    os.path.join(os.environ["LOCALAPPDATA"], "YerelAsistan") if os.environ.get("LOCALAPPDATA") else None
)
SETTINGS_DIR = Path(_local) if _local else DATA_DIR
SETTINGS_PATH = SETTINGS_DIR / "settings.json"
SHARED_SETTINGS_PATH = DATA_DIR / "settings.json"  # before 2.6; each computer starts from a copy of it
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

DEFAULTS = {
    "assistant_name": "Asistan",
    "model": "gemma3:4b",
    "whisper_model": "small",
    "whisper_device": "auto",  # "auto" = graphics card when possible, "cpu" = always the processor
    "language": "tr",
    "tts_voice": "tr-TR-EmelNeural",  # "windows" = offline Windows voice in the browser
    "auto_listen": True,  # reopen the microphone after a spoken reply
    "memory_model": "",  # model that learns facts in the background; "" = same as the chat model
    "outlook_sync": False,  # copy the admin's reminders into the Outlook calendar (3.6)
    "weather_city": "",  # city for "hava nasıl?" and the agenda's weather line (3.11)
}


def load() -> dict:
    settings = dict(DEFAULTS)
    path = SETTINGS_PATH if SETTINGS_PATH.exists() else SHARED_SETTINGS_PATH
    if path.exists():
        try:
            settings.update(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return settings


def save(changes: dict) -> dict:
    settings = load()
    settings.update({k: v for k, v in changes.items() if k in DEFAULTS and v is not None})
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings
