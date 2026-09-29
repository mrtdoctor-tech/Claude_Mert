"""Who is talking right now (voice identification, 3.0).

Until the first voice is enrolled the feature is off and everything works as before (owner ALL).
Afterwards every message belongs to the current identity: a voice profile's name, or GUEST.

Rules (decided by the user, 2026-09-29):
- A recognised voice sets the identity; typing afterwards counts as that person, with no time limit.
- An unknown voice (enough speech, below the threshold) switches to guest.
- Typing LOCK_CODE ("1234") locks: back to guest until a known voice speaks again.
- The admin (first enrolled person) may type "<Name>1234" to enter another profile's session, e.g. to test it.
- Guests may ask general questions; they never see private memories/conversations and are logged.

The identity lives in this process only: restarting the app (or an update) starts as guest.
"""

import re

from . import db

GUEST = "misafir"
LOCK_CODE = "1234"

_current: str | None = None  # name of the verified person, None = guest


def active() -> bool:
    return db.count_speakers() > 0


def _profile(name: str | None):
    if not name:
        return None
    return next((s for s in db.list_speakers() if s["name"].casefold() == name.casefold()), None)


def owner() -> str:
    """Whose data the current messages belong to (db.ALL while the feature is off)."""
    if not active():
        return db.ALL
    return _current if _profile(_current) else GUEST


def is_admin() -> bool:
    if not active():
        return True  # nobody enrolled yet: whoever sits here sets things up
    profile = _profile(_current)
    return bool(profile and profile["is_admin"])


def state() -> dict:
    who = owner()
    return {
        "active": who != db.ALL,
        "name": None if who in (db.ALL, GUEST) else who,
        "guest": who == GUEST,
        "admin": is_admin(),
    }


def verified_by_voice(name: str, score: float, scores: str = ""):
    """Every spoken message is logged with all profiles' scores, so the threshold can be tuned with real voices."""
    global _current
    event = "Ses ile tanındı" if _current != name else "Ses doğrulandı"
    _current = name
    db.log_security(event, f"{name} — {scores}" if scores else name, score)


def unknown_voice(score: float, text: str, scores: str = ""):
    global _current
    _current = None
    db.log_security("Tanınmayan ses", f"{text} — {scores}" if scores else text, score)


def handle_code(text: str) -> str | None:
    """Lock / switch codes typed on the keyboard. Returns the notice to show, or None for a normal message."""
    global _current
    if not active():
        return None
    typed = text.strip()
    if typed == LOCK_CODE:
        was = owner()
        _current = None
        db.log_security("Kilitlendi (1234)", f"{was} oturumu kapatıldı")
        return "🔒 Kilitlendi. Misafir moduna geçildi; kendi oturumuna dönmek için konuşman yeterli."
    match = re.fullmatch(r"(\S+?)" + LOCK_CODE, typed)
    if match and is_admin():
        target = _profile(match.group(1))
        if target:
            db.log_security("Yönetici oturum değiştirdi", f"{owner()} → {target['name']}")
            _current = target["name"]
            return f"👤 {target['name']} oturumuna geçildi."
    return None


def enrolled(name: str):
    """A voice was just enrolled by the person sitting here."""
    global _current
    if len(db.list_speakers()) == 1:
        # First profile: its owner is the admin and everything recorded so far is theirs.
        db.assign_unowned(name)
        _current = name
    db.log_security("Ses profili kaydedildi", name)
