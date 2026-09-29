"""Who is talking right now (voice identification, 3.0).

Until the first voice is enrolled the feature is off and everything works as before (owner ALL).
Afterwards every message belongs to the current identity: a voice profile's name, or GUEST.

Rules (decided by the user, 2026-09-29):
- A recognised voice sets the identity; typing afterwards counts as that person, with no time limit.
- An unknown voice (enough speech, below the threshold) switches to guest.
- Typing LOCK_CODE ("1234") locks: back to guest until a known voice speaks again.
- The admin (first enrolled person) may type "<Name>1234" to enter another profile's session, e.g. to test it.
- Each profile may have a personal passcode (set by the admin): typing it enters that profile without the voice,
  e.g. when a cold changes the voice. It is stored only as a salted PBKDF2 hash.
- Guests may ask general questions; they never see private memories/conversations and are logged.

The identity lives in this process only: restarting the app (or an update) starts as guest.
"""

import hashlib
import hmac
import os
import re
import time

from . import db

GUEST = "misafir"
LOCK_CODE = "1234"

PASSCODE_MIN = 6
_ITERATIONS = 200_000

MAX_TRIES = 5  # wrong single-word guesses by a guest before passcode login pauses
PAUSE_SECONDS = 600

_current: str | None = None  # name of the verified person, None = guest
_misses: list[float] = []  # times of a guest's wrong passcode attempts


def hash_passcode(code: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def _passcode_matches(code: str, stored: str | None) -> bool:
    if not stored:
        return False
    salt, digest = stored.split("$")
    test = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS)
    return hmac.compare_digest(test.hex(), digest)


def passcode_problem(code: str, speaker_id: int) -> str | None:
    """Why this passcode cannot be used, or None if it is fine."""
    if not _looks_like_passcode(code):
        return f"Şifre en az {PASSCODE_MIN} karakter olmalı, en az bir harf ve bir rakam içermeli, boşluk içermemeli."
    if LOCK_CODE in code:
        return f"Şifre {LOCK_CODE} içeremez (o kilitleme kodu)."
    for s in db.list_speakers():
        if s["id"] != speaker_id and _passcode_matches(code, s.get("passcode")):
            return "Bu şifre başka bir profilde kullanılıyor."
    return None


def _looks_like_passcode(text: str) -> bool:
    return (len(text) >= PASSCODE_MIN and not any(c.isspace() for c in text)
            and any(c.isdigit() for c in text) and any(c.isalpha() for c in text))


def _passcode_attempt(text: str) -> str | None:
    """Passcode login. Returns a notice, or None if the text is an ordinary message.

    A guest's single word with letters and digits is taken as a passcode attempt: it never reaches the model or any
    log (a near-miss would give the real passcode away). After MAX_TRIES misses passcodes pause for PAUSE_SECONDS.
    """
    global _current
    if not _looks_like_passcode(text):
        return None
    speakers = db.list_speakers()
    if not any(s.get("passcode") for s in speakers):
        return None
    guest = owner() == GUEST
    now = time.time()
    _misses[:] = [t for t in _misses if now - t < PAUSE_SECONDS]
    if guest and len(_misses) >= MAX_TRIES:
        db.log_security("Şifre denemesi engellendi", "Çok fazla yanlış deneme; bekleme süresi dolmadı")
        return f"⛔ Çok fazla yanlış şifre denendi. {PAUSE_SECONDS // 60} dakika sonra tekrar dene ya da konuş."
    found = next((s for s in speakers if _passcode_matches(text, s.get("passcode"))), None)
    if found:
        _misses.clear()
        db.log_security("Şifre ile girildi", f"{owner()} → {found['name']}")
        _current = found["name"]
        return f"🔑 Şifre doğru. {found['name']} oturumuna geçildi."
    if not guest:
        return None  # a signed-in person's word like "iPhone15" is just a message
    _misses.append(now)
    db.log_security("Yanlış şifre denemesi", f"{len(_misses)}/{MAX_TRIES}")
    if len(_misses) >= MAX_TRIES:
        db.log_security("Çok fazla şifre denemesi", f"Şifreyle giriş {PAUSE_SECONDS // 60} dakika kapatıldı")
    return "🔑 Şifre yanlış."

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
    notice = _passcode_attempt(typed)
    if notice:
        return notice
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
