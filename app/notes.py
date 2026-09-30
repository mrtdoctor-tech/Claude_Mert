"""Notes and lists (3.16): "Listeye süt ekle", "Alışveriş listesinde ne var?", "Not al: kombiyi ara".

Understood by rules like the reminders (the model is not asked), so nothing is invented or lost.
Every list belongs to one person; guests have none. A list is just a name: "alışveriş" (the default for
"listeye …"), "yapılacaklar", "notlar" (for "not al"), or anything the person says ("tatil listesine …").
"""

import re

from . import db, identity

MAX_LENGTH = 200
DEFAULT_LIST = "alışveriş"
NOTES_LIST = "notlar"
ALIASES = {"market": "alışveriş", "alış veriş": "alışveriş", "alisveris": "alışveriş", "yapılacak": "yapılacaklar",
           "yapılacak işler": "yapılacaklar", "iş": "yapılacaklar", "işler": "yapılacaklar", "not": NOTES_LIST}


def _lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


def _list_name(word: str | None) -> str:
    name = _lower((word or "").strip()) or DEFAULT_LIST
    return ALIASES.get(name, name)


def _split_items(text: str) -> list[str]:
    parts = re.split(r",|;|\s+ve\s+|\s+ile\s+|\s+bir de\s+", text)
    return [p.strip(" .!?'\"’") for p in parts if p.strip(" .!?'\"’")]


def _same(item: str, said: str) -> bool:
    """"süt" matches "sütü" / "Süt" (Turkish endings), "ekmek" matches "ekmeği"."""
    a, b = _lower(item), _lower(said)
    if a == b:
        return True
    short, long = sorted((a, b), key=len)
    stem = short[:-1] if short[-1:] in "kçtp" else short  # ekmek → ekmeğ(i)
    return len(short) >= 3 and long.startswith(stem) and len(long) - len(short) <= 3


# Commands

_W = r"[\wçğıöşü]+"
# A list's name is one word, and only before "listesi…" ("tatil listesine"); bare "listeye/listeden" is the default list,
# so in "süt ve ekmeği listeden sil" the word "ekmeği" is not taken for a list name.
_LIST_TO = rf"(?:(?:({_W})\s+)?listes\w*?(?:e|ne)|listeye|listeme)"
_ADD = re.compile(rf"^{_LIST_TO}\s+(.+?)\s+(?:ekle|yaz|koy)(?:r\s*mısın|\s*lütfen)?[.!]?$")
_ADD_AFTER = re.compile(rf"^(.+?)\s+{_LIST_TO}\s+(?:ekle|yaz|koy)")
_NOTE = re.compile(r"^(?:bunu\s+|şunu\s+)?not\s+(?:al|et|tut)\s*[:,-]?\s*(.+)$|^(.+?)\s+diye\s+not\s+(?:al|et|tut)")
_SHOW = re.compile(rf"^(?:(?:({_W})\s+)?listes\w*|listem\w*|listede)\s.*\b(ne|neler|var|göster|oku|söyle)\b"
                   r"|\b(listelerim|listeleri(?:mi)?)\s+(göster|neler|oku)|^notlar(?:ım|ımı)?\s*(ne|neler|göster|oku)?\s*\??$")
_REMOVE = re.compile(rf"^(.+?)\s+(?:(?:({_W})\s+)?listes\w*?(?:den|nden)|listeden|listemden)\s+(?:sil|çıkar|kaldır|at)")
_CLEAR = re.compile(rf"^(?:(?:({_W})\s+)?listes\w*?(?:i|ni)|listemi|listeyi)\s+(?:temizle|boşalt|sil)")

def _format_list(name: str, items: list[dict]) -> str:
    title = "Notların" if name == NOTES_LIST else f"{name.capitalize()} listesi"
    if not items:
        return f"{title} boş."
    lines = [f"**📝 {title}**"] + [f"- {'☑' if i['done'] else '☐'} {i['text']}" for i in items]
    return "\n".join(lines)


def is_command(text: str) -> bool:
    low = _lower(text.strip())
    return len(low) <= MAX_LENGTH and bool(_ADD.search(low) or _ADD_AFTER.search(low)
                                           or _NOTE.search(low) or _SHOW.search(low) or _REMOVE.search(low)
                                           or _CLEAR.search(low))


def handle(text: str, owner: str) -> str | None:
    """A reply for a notes/list command in the chat, or None if the message is something else."""
    raw = text.strip()
    low = _lower(raw)
    if not is_command(raw):
        return None
    if owner == identity.GUEST:
        return "Notlar ve listeler kişiye özel. Önce seni tanımam lazım: bir cümle söyle ya da şifreni yaz."
    who = None if owner == db.ALL else owner

    def original(part: str) -> str:
        """The same words as typed, with the person's own capitals."""
        start = low.find(part)
        return raw[start:start + len(part)] if start >= 0 else part

    m = _NOTE.search(low)
    if m:
        note = original((m.group(1) or m.group(2)).strip(" .:"))
        db.add_note(who, NOTES_LIST, note)
        return f"📝 Not aldım: {note}"

    m = _CLEAR.search(low)
    if m:
        name = _list_name(m.group(1))
        count = db.clear_list(owner, name)
        return f"🧹 {name.capitalize()} listesini temizledim ({count} şey silindi)." if count else f"{name.capitalize()} listesi zaten boş."

    m = _REMOVE.search(low)
    if m:
        name = _list_name(m.group(2))
        items = db.list_notes(owner, name)
        removed = []
        for said in _split_items(m.group(1)):
            hit = next((i for i in items if i not in removed and _same(i["text"], said)), None)
            if hit:
                db.delete_note(hit["id"])
                removed.append(hit)
        if not removed:
            return f"{name.capitalize()} listesinde \"{m.group(1)}\" bulamadım."
        left = len(items) - len(removed)
        return f"✅ Çıkardım: {', '.join(i['text'] for i in removed)}. Listede {left} şey kaldı."

    m = _SHOW.search(low)
    if m:
        if m.group(3):  # "listelerimi göster"
            names = db.list_names(owner)
            if not names:
                return "Hiç listen yok. \"Listeye süt ekle\" diyerek başlayabilirsin."
            return "\n\n".join(_format_list(n, db.list_notes(owner, n)) for n in names)
        name = NOTES_LIST if low.startswith("not") else _list_name(m.group(1))
        return _format_list(name, db.list_notes(owner, name))

    m = _ADD.search(low)
    if m:
        name, what = _list_name(m.group(1)), m.group(2)
    else:
        m = _ADD_AFTER.search(low)
        name, what = _list_name(m.group(2)), m.group(1)
    existing = db.list_notes(owner, name)
    added, already = [], []
    for item in _split_items(original(what)):
        same = next((i for i in existing if _same(i["text"], item)), None)
        if same:
            already.append(same["text"])
        else:
            db.add_note(who, name, item)
            added.append(item)
    total = len(existing) + len(added)
    reply = f"🛒 {name.capitalize()} listesine ekledim: {', '.join(added)}." if added else ""
    if already:
        reply += f" Zaten listede: {', '.join(already)}."
    return (reply + f" Listede {total} şey var.").strip()
