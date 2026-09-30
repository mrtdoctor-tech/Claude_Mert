"""Own words (3.28): names Whisper does not know, like "HourGlow".

Whisper writes an English name said in a Turkish sentence the Turkish way ("Avır glo", "Aurglo", "hour glow"), and
then "HourGlow Takip dosyasını Excel'de aç" finds no file. The words in the setting `vocabulary` (comma separated,
"HourGlow" by default) are
- given to Whisper as words to expect (with the assistant's name, see wake.hotwords), and
- put back into the heard text when one, two or three heard words sound like them: compared by their consonants
  (vowels and the soft h/w/v/y sounds are what Turkish spelling changes most) and then by overall likeness.
"""

import re
from difflib import SequenceMatcher

from . import config

_FOLD = str.maketrans("çğıöşüâîû", "chiosuaiu")  # ğ is soft like h: "Ağır glo" is also "HourGlow"
_SOFT = set("aeiouhwvy")
SIMILAR = 0.6


def words(settings: dict | None = None) -> list[str]:
    settings = settings or config.load()
    return [w.strip() for w in (settings.get("vocabulary") or "").split(",") if w.strip()]


def _plain(text: str) -> str:
    low = text.replace("I", "ı").replace("İ", "i").lower().translate(_FOLD)
    low = low.replace("ou", "a").replace("ow", "o").replace("gh", "")
    return re.sub(r"[^a-z0-9]", "", low)


def _skeleton(plain: str) -> str:
    return "".join(c for c in plain if c not in _SOFT)


def _sounds_like(heard: str, term: str) -> bool:
    a, b = _plain(heard), _plain(term)
    if not a or not b:
        return False
    if a == b:
        return True
    return _skeleton(a) == _skeleton(b) and len(_skeleton(b)) >= 2 and SequenceMatcher(None, a, b).ratio() >= SIMILAR


_TOKEN = re.compile(r"[\wçğıöşüÇĞİÖŞÜ]+(?:['’][\wçğıöşü]+)?")


def fix(text: str, settings: dict | None = None) -> str:
    """"Avır glo takip dosyasını aç" → "HourGlow takip dosyasını aç" (Turkish endings after an apostrophe are kept)."""
    terms = words(settings)
    if not text or not terms:
        return text
    tokens = list(_TOKEN.finditer(text))
    out, last, i = [], 0, 0
    while i < len(tokens):
        replaced = False
        for size in (3, 2, 1):
            group = tokens[i:i + size]
            if len(group) < size:
                continue
            last_word = group[-1].group()
            stem, _, ending = last_word.partition("'") if "'" in last_word else last_word.partition("’")
            heard = " ".join(t.group() for t in group[:-1]) + " " + stem
            for term in terms:
                if heard.strip().lower() != term.lower() and _sounds_like(heard, term):
                    out.append(text[last:group[0].start()])
                    out.append(term + (f"'{ending}" if ending else ""))
                    last, i, replaced = group[-1].end(), i + size, True
                    break
            if replaced:
                break
        if not replaced:
            i += 1
    out.append(text[last:])
    return "".join(out)
