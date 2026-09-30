"""Wake word (3.19): say "Asiye" (or "Merhaba Asiye, saat kaç?") instead of pressing the microphone button.

The browser keeps the microphone open and sends every short burst of speech here; Whisper (the same local model as
the microphone button) turns it into text and this module checks whether it starts with the wake phrase. Nothing
leaves the computer, and speech without the wake phrase is thrown away without being logged or saved.

Whisper writes names a little differently now and then ("Asya", "Asiye'", "Asiyecim"), so the words are compared
loosely. The phrase must be at the start (after at most one greeting such as "hey" or "merhaba"): a sentence that
only mentions the name in the middle ("dün Asiye'yle konuştum") does not wake the assistant.
"""

import re
from difflib import SequenceMatcher

GREETINGS = {"hey", "hei", "ey", "merhaba", "selam", "hop", "alo", "bak", "sevgili", "canım"}
# How alike a heard word must be to the wake word (0..1). A one-word phrase must be close ("Aziye" 0.8 passes, "Ayşe"
# and "Asya" 0.67 do not: both are real names); with two words ("Merhaba Asiye") the pair is rare enough to be looser.
SIMILAR_ONE = 0.75
SIMILAR_MORE = 0.6
_WORD = r"[\wçğıöşüâîûÇĞİÖŞÜÂÎÛ]+(?:['’][\wçğıöşüâîû]+)?"  # "Asiye'ye" is one word
_FOLD = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def _words(text: str) -> list[str]:
    low = text.replace("I", "ı").replace("İ", "i").lower()
    return re.findall(_WORD, low)


def _fold(word: str) -> str:
    return word.translate(_FOLD)


def _alike(heard: str, wanted: str, similar: float) -> bool:
    a, b = _fold(heard).replace("'", "").replace("’", ""), _fold(wanted)
    if a == b or (a.startswith(b) and len(a) - len(b) <= 5):  # "asiyecim", "asiye'ciğim"
        return True
    return SequenceMatcher(None, a, b).ratio() >= similar


def phrase_for(settings: dict) -> str:
    return (settings.get("wake_phrase") or "").strip() or settings.get("assistant_name") or "Asistan"


_ENGLISH = {"the", "and", "you", "i", "i'm", "im", "me", "my", "is", "are", "was", "to", "of", "it", "in", "on", "for",
            "with", "that", "this", "what", "here", "there", "since", "let", "out", "your", "we", "be", "so", "love",
            "baby", "just", "don't", "can't", "all", "no", "oh", "yeah", "when", "like", "know", "got", "get", "go"}


def sounds_foreign(text: str, language: str | None) -> bool:
    """Heard speech in another language while the assistant speaks Turkish: song lyrics from music (3.21).

    Used only where nobody pressed the button (wake word, reopened microphone), so a deliberate English question
    typed or spoken with the button still works.
    """
    if (language or "") != "tr":
        return False
    words = re.findall(r"[a-zçğıöşü']+", text.replace("I", "ı").replace("İ", "i").lower().replace("ı'm", "i'm"))
    if len(words) < 3 or re.search(r"[çğıöşü]", " ".join(w for w in words if w not in ("ı", "ı'm"))):
        return False
    english = sum(w.replace("ı", "i") in _ENGLISH for w in words)
    return english / len(words) >= 0.25


def hotwords(settings: dict) -> str:
    """Words Whisper is told to expect: the assistant's name and the wake phrase (3.20).

    Without this, a quickly said "Merhaba Asiye" came out as "Merhaba size".
    """
    words = [settings.get("assistant_name") or "", (settings.get("wake_phrase") or "").strip()]
    return " ".join(dict.fromkeys(w for w in words if w))


def match(text: str, phrase: str) -> tuple[bool, str]:
    """(woken?, the rest of the sentence after the wake phrase).

    A one-word phrase ("Asiye") must open the sentence, so talk that only mentions the name does not wake. A longer
    phrase ("Merhaba Asiye") may come anywhere (3.22): with music playing, the burst never goes quiet and the phrase
    lands in the middle of several seconds of song.
    """
    heard, wanted = _words(text), _words(phrase)
    if not heard or not wanted:
        return False, ""
    similar = SIMILAR_ONE if len(wanted) == 1 else SIMILAR_MORE
    starts = range(len(heard)) if len(wanted) > 1 else (0, 1)
    for skip in starts:
        if skip and len(wanted) == 1 and heard[0] not in GREETINGS:
            continue
        part = heard[skip:skip + len(wanted)]
        if len(part) == len(wanted) and all(_alike(h, w, similar) for h, w in zip(part, wanted)):
            return True, _rest(text, skip + len(wanted))
    return False, ""


def _rest(text: str, count: int) -> str:
    """The original text after the first `count` words, with its own capitals and punctuation."""
    found = list(re.finditer(_WORD, text))
    if len(found) <= count:
        return ""
    rest = text[found[count].start():].strip()
    return rest[:1].upper() + rest[1:]
