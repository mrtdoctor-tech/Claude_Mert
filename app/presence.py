"""Warns when the shared database is also open on another computer.

The data folder can be synced between computers (OneDrive). SQLite is not safe to use from two
computers at once, so each running assistant regularly writes its computer name here, and a
fresh note from another computer means "someone else has it open right now".
"""

import asyncio
import json
import socket
import time

from .config import DATA_DIR

PATH = DATA_DIR / "kullanimda.json"
INTERVAL = 60  # seconds between notes
FRESH = 150  # a note younger than this means the other computer is still running

HOST = socket.gethostname()


def other_computer() -> str | None:
    """Name of another computer that has the assistant open right now, if any."""
    try:
        note = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if note.get("host") != HOST and time.time() - note.get("time", 0) < FRESH:
        return note.get("host")
    return None


def _write():
    try:
        PATH.write_text(json.dumps({"host": HOST, "time": time.time()}), encoding="utf-8")
    except OSError:
        pass


async def keep_marking():
    while True:
        if other_computer() is None:  # never overwrite the other computer's note
            _write()
        await asyncio.sleep(INTERVAL)


def clear():
    """On shutdown: remove our note so the other computer does not wait for it to expire."""
    try:
        if json.loads(PATH.read_text(encoding="utf-8")).get("host") == HOST:
            PATH.unlink()
    except (OSError, ValueError):
        pass
