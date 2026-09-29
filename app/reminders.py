"""Reminders, alarms and timers (3.5): "20 dakikalık sayaç kur", "yarın 7'de uyandır", "15 Ekim'de ... hatırlat".

Times are understood by these rules, never by the model (small models get times wrong).
Every reminder belongs to one person (the current identity); guests cannot create any.
A background loop (`run`) turns due reminders into alerts; the page shows them, and when no page is open
a Windows notification is shown instead.
"""

import asyncio
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timedelta
from xml.sax.saxutils import escape

from . import db, identity
from .quick import DAYS_TR, MONTHS_TR

log = logging.getLogger("asistan.reminders")

MAX_LENGTH = 160  # longer messages are left to the model
DEFAULT_HOUR = 9  # a date without a time: 09:00
MISSED_AFTER = 120  # seconds: an alert fired this late happened while the assistant was closed

_last_poll = 0.0  # when a page last asked for alerts; if long ago, nobody sees the page


def _lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


# Number words → digits ("yirmi beş dakika" → "25 dakika", "yarım saat" → "30 dakika")

_UNITS = {"bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9}
_TENS = {"on": 10, "yirmi": 20, "otuz": 30, "kırk": 40, "elli": 50, "altmış": 60}


def _numbers(text: str) -> str:
    text = re.sub(r"\byarım\s+saat", "30 dakika", text)
    text = re.sub(r"\bçeyrek\s+saat", "15 dakika", text)

    def tens_units(m):
        return str(_TENS[m.group(1)] + (_UNITS[m.group(2)] if m.group(2) else 0))

    tens, units = "|".join(_TENS), "|".join(_UNITS)
    text = re.sub(rf"\b({tens})(?:\s+({units}))?\b", tens_units, text)
    text = re.sub(rf"\b({units})\b(?=\s*(?:buçuk|saniye|sn|dakika|dk|saat|gün|hafta|ay\b|yıl|\d|'|’|[:.]))",
                  lambda m: str(_UNITS[m.group(1)]), text)
    return text


# Pieces of a request

_TRIGGER = re.compile(r"hatırlat|haber ver|uyar\b|uyar(?:ır|ır mısın)|uyandır|alarm|sayaç|zamanlayıcı|geri sayım|timer")
_DURATION = re.compile(
    r"(\d+(?:[.,]\d+)?)(\s*buçuk)?\s*(saniye|sn|dakika|dk|saat|gün)(?:lık|lik|luk|lük)?(?:\s*(?:sonra|içinde|geçince))?")
_WEEKDAYS = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]
_MONTHS = [m.lower().replace("ş", "ş") for m in ("ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz",
                                                  "ağustos", "eylül", "ekim", "kasım", "aralık")]
_SUFFIX = r"(?:['’]?(?:de|da|te|ta|den|dan|ten|tan|ye|ya|e|a|ında|inde|unda|ünde|ı|i|u|ü))?"
_DATE = re.compile(rf"\b(\d{{1,2}})\s+({'|'.join(_MONTHS)}){_SUFFIX}(?:\s+(\d{{4}}){_SUFFIX})?\b")
_NUMDATE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b")
_CLOCK = re.compile(
    r"(?<![\d:.])(saat\s+)?(\d{1,2})(?:[:.](\d{2})|\s*(buçuk)\w*)?(['’]?(?:de|da|te|ta|ye|ya|e|a|ı|i|u|ü)(?:ki)?)?"
    r"(?![\d\w])")
_PERIOD = re.compile(r"\b(sabah|öğlen|öğle|öğleden sonra|akşam|gece)(?:ı|leyin|ları|leri)?\b")
_DAYWORD = re.compile(r"\b(bugün|yarından sonra|öbür gün|yarın)\b")
_WEEKDAY = re.compile(rf"\b(?:(her)\s+)?({'|'.join(_WEEKDAYS)})(?:y[ıie]|[ıi]|den|dan|ler[ie]?)?\b")
_REPEAT = re.compile(r"\bher\s+(gün|sabah|akşam|hafta|ay|yıl|sene)\b")

_FILLER = re.compile(
    r"\b(bana|beni|lütfen|bir|kur|kurar\s+mısın|kurabilir\s+misin|ayarla|başlat|için|sonra|diye|de|da|mısın|misin|"
    r"musun|müsün|ver|saat|hatırlatır|hatırlatır mısın|hatırlatma|hatırlat|haber|uyar|uyarır|uyandır|alarm|alarmı|"
    r"sayaç|sayacı|zamanlayıcı|geri\s+sayım|kurulsun|olsun|ki|ve)\b")


def _next_weekday(now: datetime, weekday: int, hour: int, minute: int) -> datetime:
    days = (weekday - now.weekday()) % 7
    when = (now + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return when if when > now else when + timedelta(days=7)


def _advance(when: datetime, repeat: str) -> datetime:
    if repeat == "daily":
        return when + timedelta(days=1)
    if repeat == "weekly":
        return when + timedelta(days=7)
    if repeat == "monthly":
        month = when.month % 12 + 1
        year = when.year + (when.month == 12)
        day = min(when.day, 28 if month == 2 else 30 if month in (4, 6, 9, 11) else 31)
        return when.replace(year=year, month=month, day=day)
    if repeat == "yearly":
        try:
            return when.replace(year=when.year + 1)
        except ValueError:  # 29 February
            return when.replace(year=when.year + 1, day=28)
    return when


def parse(text: str, now: datetime | None = None) -> dict | None:
    """{"kind", "due" (datetime), "repeat" (None/daily/weekly/monthly/yearly), "text"} or None if not a request."""
    now = now or datetime.now()
    raw = _lower(text.strip())
    if len(raw) > MAX_LENGTH or not _TRIGGER.search(raw):
        return None
    t = _numbers(raw)
    spans = []  # parts of the message that describe the time, removed from the reminder text

    kind = "alarm" if re.search(r"uyandır|alarm", t) else "reminder"
    due = None
    repeat = None

    # 1) "20 dakika", "1 saat 30 dakika", "2 buçuk saat": a timer (relative time)
    total, duration_spans = 0.0, []
    for m in _DURATION.finditer(t):
        value = float(m.group(1).replace(",", "."))
        if m.group(2):
            value += 0.5
        total += value * {"saniye": 1, "sn": 1, "dakika": 60, "dk": 60, "saat": 3600, "gün": 86400}[m.group(3)]
        duration_spans.append(m.span())
    if total and not _DATE.search(t) and not _NUMDATE.search(t) and not _DAYWORD.search(t):
        spans += duration_spans
        due = now + timedelta(seconds=total)
        if kind != "alarm":
            kind = "timer"
    else:
        # 2) Absolute: day + clock time
        day = None
        m = _DATE.search(t) or None
        if m:
            month = _MONTHS.index(m.group(2)) + 1
            year = int(m.group(3)) if m.group(3) else now.year
            try:
                day = datetime(year, month, int(m.group(1)))
            except ValueError:
                return None
            spans.append(m.span())
            if not m.group(3) and day.date() < now.date():
                day = day.replace(year=now.year + 1)
        m = _NUMDATE.search(t)
        if not day and m:
            try:
                day = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                return None
            spans.append(m.span())
        m = _DAYWORD.search(t)
        if not day and m:
            offset = {"bugün": 0, "yarın": 1, "öbür gün": 2, "yarından sonra": 2}[m.group(1)]
            day = now + timedelta(days=offset)
            spans.append(m.span())
        weekday = None
        m = _WEEKDAY.search(t)
        if not day and m:
            weekday = _WEEKDAYS.index(m.group(2))
            if m.group(1):
                repeat = "weekly"
            spans.append(m.span())
        m = _REPEAT.search(t)
        if m:
            repeat = {"gün": "daily", "sabah": "daily", "akşam": "daily", "hafta": "weekly", "ay": "monthly",
                      "yıl": "yearly", "sene": "yearly"}[m.group(1)]
            spans.append(m.span())

        hour = minute = None
        p = _PERIOD.search(t)
        for m in _CLOCK.finditer(t):
            if any(a <= m.start() < b for a, b in spans):
                continue  # "15" of "15 ekim"
            before = t[:m.start()].rstrip()
            after_period = bool(p) and before.endswith(p.group(1))
            if not (m.group(1) or m.group(3) or m.group(4) or m.group(5) or after_period):
                continue  # a bare number is not a time
            h = int(m.group(2))
            if h > 24 or (m.group(3) and int(m.group(3)) > 59):
                continue
            hour, minute = h % 24, int(m.group(3)) if m.group(3) else (30 if m.group(4) else 0)
            spans.append(m.span())
            break
        if p:
            spans.append(p.span())
            if hour is None:
                hour = {"sabah": 8, "öğlen": 12, "öğle": 12, "öğleden sonra": 15, "akşam": 19, "gece": 22}[p.group(1)]
                minute = 0
            elif p.group(1) in ("öğleden sonra", "akşam") and hour < 12:
                hour += 12
            elif p.group(1) == "gece" and 6 <= hour < 12:
                hour += 12
        if hour is None and day is None and weekday is None:
            return None
        if hour is None:
            hour, minute = DEFAULT_HOUR, 0

        if weekday is not None:
            due = _next_weekday(now, weekday, hour, minute)
        elif day is not None:
            due = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if due <= now:
                if not repeat:
                    return {"kind": kind, "due": due, "repeat": None, "text": "", "past": True}
                while due <= now:
                    due = _advance(due, repeat)
        else:
            due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            wake = "uyandır" in t  # "7 buçukta uyandır" means the morning
            if due <= now and not p and not wake and 1 <= hour < 12 and due + timedelta(hours=12) > now:
                due += timedelta(hours=12)  # "saat 3'te" at 14:00 means 15:00
            while due <= now:
                due = _advance(due, repeat or "daily")

    # What to remind: the message without its time words and request words
    kept = list(t)
    for a, b in spans:
        for i in range(a, b):
            kept[i] = " "
    what = _FILLER.sub(" ", "".join(kept))
    what = re.sub(r"[?!.,;:]+|(?<!\w)['’]|['’](?!\w)", " ", what)
    # keep the user's own capitals ("Sezin'in"), the matching above worked on lower case
    originals = {_lower(w): w for w in re.findall(r"[\w'’]+", text)}
    what = " ".join(originals.get(w, w) for w in what.split())
    return {"kind": kind, "due": due, "repeat": repeat, "text": what}


# Wording

def when_text(due: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    clock = f"{due:%H:%M}"
    if due.date() == now.date():
        return f"bugün saat {clock}"
    if due.date() == (now + timedelta(days=1)).date():
        return f"yarın saat {clock}"
    year = f" {due.year}" if due.year != now.year else ""
    return f"{due.day} {MONTHS_TR[due.month - 1]}{year} {DAYS_TR[due.weekday()]}, saat {clock}"


def duration_text(seconds: float) -> str:
    seconds = int(round(seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    parts = [f"{h} saat" if h else "", f"{m} dakika" if m else "", f"{s} saniye" if s and not h else ""]
    return " ".join(p for p in parts if p) or "0 saniye"


REPEAT_TR = {"daily": "her gün", "weekly": "her hafta", "monthly": "her ay", "yearly": "her yıl"}


def _lik(word: str) -> str:
    """Turkish vowel harmony: dakikalık, saniyelik, saatlik."""
    if word.endswith("saat"):
        return "lik"  # a loanword: "saatlik"
    last = next((c for c in reversed(word) if c in "aıeiouöü"), "a")
    return {"a": "lık", "ı": "lık", "e": "lik", "i": "lik", "o": "luk", "u": "luk", "ö": "lük", "ü": "lük"}[last]


def label(item: dict) -> str:
    if item["text"]:
        return item["text"]
    return {"timer": "Sayaç", "alarm": "Alarm"}.get(item["kind"], "Hatırlatma")


# Chat commands

_LIST = re.compile(r"(hatırlatma|hatırlatıcı|alarm|sayaç)(lar|ları)(ım|ımı)?\b.*\b(ne|neler|göster|listele|var)"
                   r"|\b(ne|neler)\b.*\bhatırlatma")
_CANCEL = re.compile(r"(sayac|sayaç|alarm|hatırlatma|zamanlayıcı)\w*\s+(?:\w+\s+)?(iptal|sil|kapat|durdur|kaldır)")
_LEFT = re.compile(r"(sayaç|sayac|süre)\w*\s+(ne\s+kadar|kaç\s+dakika|kaç\s+saniye)\s*(kaldı|var)"
                   r"|\b(ne\s+kadar|kaç\s+dakika)\s+kaldı")


def is_command(text: str) -> bool:
    low = _lower(text.strip())
    return len(low) <= MAX_LENGTH and bool(_LIST.search(low) or _CANCEL.search(low) or _LEFT.search(low)
                                           or parse(text))


def handle(text: str, owner: str, now: datetime | None = None) -> str | None:
    """A reply for reminder commands in the chat, or None if the message is something else."""
    now = now or datetime.now()
    low = _lower(text.strip())
    if len(low) > MAX_LENGTH:
        return None
    is_list, is_cancel, is_left = _LIST.search(low), _CANCEL.search(low), _LEFT.search(low)
    parsed = None if (is_list or is_cancel or is_left) else parse(text, now)
    if not (is_list or is_cancel or is_left or parsed):
        return None
    if owner == identity.GUEST:
        return ("Hatırlatıcılar kişiye özel. Önce seni tanımam lazım: bir cümle söyle ya da şifreni yaz. "
                "Genel sorularına yine cevap verebilirim.")
    who = None if owner == db.ALL else owner
    active = db.list_reminders(owner)

    if is_left:
        timers = [r for r in active if r["kind"] == "timer"]
        if not timers:
            return "Çalışan bir sayaç yok."
        return " ".join(f"{label(r)}: {duration_text((_dt(r['due_at']) - now).total_seconds())} kaldı."
                        for r in timers)
    if is_list:
        if not active:
            return "Kurulu bir hatırlatman yok."
        lines = [f"- {label(r)} — {when_text(_dt(r['due_at']), now)}"
                 + (f" ({REPEAT_TR[r['repeat']]})" if r["repeat"] else "") for r in active]
        return "Hatırlatmaların:\n" + "\n".join(lines)
    if is_cancel:
        word = is_cancel.group(1)
        kind = "timer" if word.startswith(("sayac", "sayaç", "zamanlayıcı")) else "alarm" if word == "alarm" else None
        targets = [r for r in active if kind is None or r["kind"] == kind]
        if not targets:
            return "İptal edilecek bir şey bulamadım."
        if not re.search(r"\b(hepsi|hepsini|tüm|bütün)\b", low):
            targets = targets[-1:] if kind == "timer" else sorted(targets, key=lambda r: r["due_at"])[:1]
        for r in targets:
            db.set_reminder_status(r["id"], "cancelled")
        return "İptal ettim: " + ", ".join(label(r) for r in targets) + "."

    if parsed.get("past"):
        return f"{when_text(parsed['due'], now)} geçmişte kaldı; ileri bir zaman söyler misin?"
    due = parsed["due"]
    if parsed["kind"] == "timer" and not parsed["text"]:
        length = duration_text((due - now).total_seconds())
        parsed["text"] = f"{length}{_lik(length)} sayaç"
    db.add_reminder(who, parsed["kind"], parsed["text"], due.strftime("%Y-%m-%d %H:%M:%S"), parsed["repeat"])
    if parsed["kind"] == "timer":
        return f"⏳ Tamam, {duration_text((due - now).total_seconds())} sonra ({due:%H:%M}) haber vereceğim."
    repeat = f", {REPEAT_TR[parsed['repeat']]}" if parsed["repeat"] else ""
    what = f": {parsed['text']}" if parsed["text"] else ""
    icon = "⏰" if parsed["kind"] == "alarm" else "🔔"
    return f"{icon} Tamam, {when_text(due, now)}{repeat} hatırlatacağım{what}."


def _dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


# Firing

def fire_due(now: datetime | None = None) -> list[dict]:
    """Turn due reminders into alerts (repeating ones move to their next time). Returns the new alerts."""
    now = now or datetime.now()
    fired = []
    for r in db.due_reminders(now.strftime("%Y-%m-%d %H:%M:%S")):
        db.add_alert(r)
        fired.append(r)
        if r["repeat"]:
            nxt = _dt(r["due_at"])
            while nxt <= now:
                nxt = _advance(nxt, r["repeat"])
            db.move_reminder(r["id"], nxt.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            db.set_reminder_status(r["id"], "done")
    return fired


def visible_text(alert: dict) -> str:
    """Someone else's reminder rings too, but its text is only shown to its owner."""
    who = identity.owner()
    if alert["owner"] and who != db.ALL and alert["owner"] != who:
        return f"{alert['owner']} için bir hatırlatma var."
    return label(alert)


def page_polled():
    global _last_poll
    _last_poll = time.time()


def _windows_notification(title: str, body: str):
    if os.name != "nt":
        return
    xml = (f'<toast scenario="reminder"><visual><binding template="ToastGeneric"><text>{escape(title)}</text>'
           f'<text>{escape(body)}</text></binding></visual>'
           '<actions><action content="Tamam" arguments="dismiss" activationType="system"/></actions>'
           '<audio src="ms-winsoundevent:Notification.Reminder"/></toast>')
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml($env:ASISTAN_TOAST);"
        "$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe';"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show("
        "[Windows.UI.Notifications.ToastNotification]::new($x))"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       env={**os.environ, "ASISTAN_TOAST": xml}, timeout=20, capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:
        log.warning("Windows bildirimi gösterilemedi: %s", e)


async def run():
    """Background loop: fire due reminders every few seconds."""
    while True:
        try:
            fired = fire_due()
            if fired and time.time() - _last_poll > 20:  # no page is open to show them
                texts = [visible_text(r) for r in fired]
                title = "⏰ Yerel Asistan" if len(fired) == 1 else f"⏰ Yerel Asistan: {len(fired)} hatırlatma"
                await asyncio.to_thread(_windows_notification, title, " · ".join(texts))
        except Exception:
            log.exception("Hatırlatıcı döngüsü hata verdi")
        await asyncio.sleep(3)
