"""Searching old conversations (3.30).

Two ways in:
- the search box above the conversation list (`search`): conversations whose messages or title contain all the typed
  words (Turkish letters and endings ignored), with the matching sentence;
- a question in the chat (`is_question` / `context`): "Geçen hafta doktor hakkında ne konuşmuştuk?" → the messages
  of earlier conversations that best match (optionally only from the time said: dün, geçen hafta, geçen ay, 3 gün önce,
  Eylül'de…) are given to the model with the question, and the answer ends with the conversations it came from.
Only the person's own conversations are searched; guests cannot search.
"""

import math
import re
from datetime import date, datetime, timedelta

from . import db, identity

_FOLD = str.maketrans("çğıöşüâîû", "cgiosuaiu")
_STOP = {"bir", "bu", "şu", "ve", "ile", "için", "ne", "neler", "nedir", "var", "mı", "mi", "mu", "mü", "da", "de",
         "ben", "sen", "biz", "hakkında", "hakkinda", "konuda", "konusunda", "üzerine", "diye", "daha", "önce", "önceki",
         "geçen", "gecen", "hafta", "haftaki", "ay", "ayki", "dün", "dünkü", "bugün", "bugünkü", "sohbet", "sohbette",
         "sohbetlerde", "sohbetimizde", "konuştuk", "konuşmuştuk", "konuştuğumuz", "bahsettik", "bahsetmiştik",
         "bahsettiğimiz", "demiştim", "dedim", "söylemiştim", "söyledim", "sormuştum", "sordum", "hatırlıyor", "musun",
         "hatırla", "neydi", "ara", "bul", "göster", "asiye", "the", "and", "what", "gün", "günü", "günler", "evvel",
         "konuşmuş", "muyduk", "mıydık", "miydik", "eski", "geçmiş", "hiç",
         "ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık",
         "pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"}
_QUESTION = re.compile(
    r"\b(konuşmuştuk|konuştuk|konuştuğumuz|konuşmuş|bahsetmiştik|bahsettik|bahsettiğimiz|demiştim|söylemiştim|"
    r"sormuştum|anlatmıştım|konuşmuştuk)\b|\bdaha önce\b.*\b(konuş|bahset|söyle|sor)|"
    r"\b(eski|önceki|geçmiş)\s+sohbet\w*\b.*\b(ara|bul|bak)|\bsohbetlerde\s+(ara|bul)")
MONTHS = ["ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık"]
DAYS = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]
MAX_CONTEXT_CHARS = 9000


def _lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


def _stems(text: str, drop_stop: bool = True) -> list[str]:
    words = re.findall(r"[\wçğıöşü]+", _lower(text))
    return [w.translate(_FOLD)[:5] for w in words if len(w) >= 3 and not (drop_stop and w in _STOP)]


def is_question(text: str) -> bool:
    return len(text) <= 200 and bool(_QUESTION.search(_lower(text)))


def time_range(text: str, today: date | None = None) -> tuple[date | None, date | None, str]:
    """(from, until (exclusive), words for the answer) for "dün", "geçen hafta", "3 gün önce", "Eylül'de"…"""
    today = today or date.today()
    low = _lower(text)
    monday = today - timedelta(days=today.weekday())
    if re.search(r"\bbugün", low):
        return today, today + timedelta(days=1), "bugün"
    if re.search(r"\bdün", low):
        return today - timedelta(days=1), today, "dün"
    if re.search(r"\b(evvelsi gün|öbür gün|önceki gün)", low):
        return today - timedelta(days=2), today - timedelta(days=1), "evvelsi gün"
    m = re.search(r"\b(\d+|bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz|on)\s+(gün|hafta|ay)\s+(önce|evvel)", low)
    if m:
        words = {"bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10}
        n = int(m[1]) if m[1].isdigit() else words[m[1]]
        span = {"gün": 1, "hafta": 7, "ay": 30}[m[2]]
        center = today - timedelta(days=n * span)
        pad = {"gün": 1, "hafta": 4, "ay": 10}[m[2]]
        return center - timedelta(days=pad), center + timedelta(days=pad + 1), m[0]
    if re.search(r"\bbu hafta", low):
        return monday, today + timedelta(days=1), "bu hafta"
    if re.search(r"\bgeçen hafta", low):
        return monday - timedelta(days=7), monday, "geçen hafta"
    first = today.replace(day=1)
    if re.search(r"\bbu ay", low):
        return first, today + timedelta(days=1), "bu ay"
    if re.search(r"\bgeçen ay", low):
        previous = (first - timedelta(days=1)).replace(day=1)
        return previous, first, "geçen ay"
    for number, day in enumerate(DAYS):
        if re.search(rf"\b(geçen\s+)?{day}(\s+günü)?\b", low):
            back = (today.weekday() - number) % 7 or 7
            when = today - timedelta(days=back)
            return when, when + timedelta(days=1), f"geçen {day}"
    for number, month in enumerate(MONTHS, 1):
        if re.search(rf"\b{month}", low):
            year = today.year if number <= today.month else today.year - 1
            start = date(year, number, 1)
            end = date(year + (number == 12), number % 12 + 1, 1)
            return start, end, month.capitalize()
    return None, None, ""


def _matches(owner: str, words: list[str], since=None, until=None, skip=None) -> list[tuple[float, dict]]:
    rows = db.search_messages(owner, since.isoformat() if since else None, until.isoformat() if until else None, skip)
    # earlier "ne konuşmuştuk?" questions and their answers are not what was talked about
    rows = [r for r in rows if not (r["role"] == "user" and is_question(r["content"]))
            and "🔎 Kaynak sohbetler" not in r["content"]]
    if not words:
        return [(0.0, r) for r in rows]
    stems = [_stems(r["content"] + " " + r["title"], drop_stop=False) for r in rows]
    found = []
    for row, have in zip(rows, stems):
        score = 0.0
        for word in set(words):
            hits = sum(1 for s in have if s.startswith(word) or word.startswith(s) and len(s) >= 4)
            if hits:
                spread = sum(1 for h in stems if word in h) or 1
                score += (1 + math.log(hits)) * math.log(1 + len(rows) / spread)
        if score:
            found.append((score, row))
    return found


def _snippet(text: str, words: list[str], width: int = 140) -> str:
    plain = " ".join(text.split())
    folded = _lower(plain).translate(_FOLD)
    at = min((i for i in (folded.find(w) for w in words) if i >= 0), default=0)
    start = max(0, at - width // 3)
    part = plain[start:start + width]
    return ("…" if start else "") + part + ("…" if start + width < len(plain) else "")


def search(owner: str, query: str) -> list[dict]:
    """For the search box: one line per conversation, best first. Every typed word must appear somewhere in the
    conversation (its title or any message); the shown sentence is the message that matches best."""
    words = [w.translate(_FOLD) for w in re.findall(r"[\wçğıöşü]+", _lower(query)) if len(w) >= 2]
    if not words:
        return []
    by_conversation: dict[int, list[dict]] = {}
    for row in db.search_messages(owner):
        by_conversation.setdefault(row["conversation_id"], []).append(row)
    results = []
    for rows in by_conversation.values():
        texts = [_lower(r["content"]).translate(_FOLD) for r in rows]
        title = _lower(rows[0]["title"]).translate(_FOLD)
        if not all(any(w in t for t in texts) or w in title for w in words):
            continue
        hits = [sum(t.count(w) for w in words) for t in texts]
        best = max(range(len(rows)), key=lambda i: (hits[i], rows[i]["id"]))
        results.append((sum(hits), rows[best]))
    results.sort(key=lambda item: -item[1]["id"])  # newest conversations first
    return [{"conversation_id": r["conversation_id"], "title": r["title"], "message_id": r["id"], "role": r["role"],
             "created_at": r["created_at"], "snippet": _snippet(r["content"], words)} for _, r in results[:40]]


def refusal(owner: str) -> str | None:
    if owner == identity.GUEST:
        return "Eski sohbetlerde arama yalnızca sesinden ya da şifresinden tanıdığım kişiler için."
    return None


def context(owner: str, question: str, current: int | None) -> tuple[str, list[dict], str]:
    """(text for the model, the conversations it came from, the time said) for a question about earlier talks."""
    since, until, when = time_range(question)
    words = _stems(question)
    found = _matches(owner, words, since, until, current)
    if not words and since:  # "Dün ne konuşmuştuk?": everything from that time
        found = [(1.0, r) for _, r in found]
    found.sort(key=lambda item: -item[0])
    chosen, used, sources = [], 0, {}
    for _, row in found:
        text = " ".join(row["content"].split())[:900]
        if used + len(text) > MAX_CONTEXT_CHARS:
            break
        chosen.append(row)
        used += len(text)
        sources.setdefault(row["conversation_id"], row)
    chosen.sort(key=lambda r: r["id"])
    lines = [f"[{datetime.fromisoformat(r['created_at']):%d.%m.%Y %H:%M} · \"{r['title']}\" · "
             f"{'kullanıcı' if r['role'] == 'user' else 'asistan'}] {' '.join(r['content'].split())[:900]}"
             for r in chosen]
    return "\n".join(lines), list(sources.values()), when
