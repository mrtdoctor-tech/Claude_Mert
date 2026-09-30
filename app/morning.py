"""Morning summary (3.31): "Günaydın Asiye" → the day at a glance.

Put together by rules, not by the model (quick, nothing made up): date and time, the weather in the settings' city,
today's Outlook appointments and reminders, the shopping and to-do lists, and three headlines. Guests get only the
greeting and the date (the rest is personal, and the internet parts are closed to guests).
"""

import logging
import re
from datetime import date, datetime, timedelta

from . import config, db, identity, online, outlook

log = logging.getLogger("asistan.morning")

DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
_COMMAND = re.compile(
    r"^(günaydın|gunaydin|günaydınlar)(\s+[\wçğıöşü]+){0,2}$"
    r"|\b(sabah|günün|günlük)\s+özet\w*|\bbugün\w*\s+(neler\s+var|ne\s+var|programım|planım|ajandam)"
    r"|\bbugünkü\s+(program|plan|ajanda)\w*")


def is_command(text: str) -> bool:
    low = re.sub(r"[^\wçğıöşü\s]", " ", text.replace("I", "ı").replace("İ", "i").lower())
    low = " ".join(low.split())
    return len(low) <= 60 and bool(_COMMAND.search(low))


def _greeting(owner: str, now: datetime) -> str:
    name = "" if owner in (db.ALL, identity.GUEST) else f" {owner}"
    hello = "Günaydın" if now.hour < 12 else "Merhaba"
    return (f"☀️ **{hello}{name}!** Bugün {now.day} {MONTHS[now.month - 1]} {now.year}, {DAYS[now.weekday()]}; "
            f"saat {now:%H:%M}.")


def _weather() -> str | None:
    try:
        w = online.weather_summary()
    except Exception as e:
        log.warning("Sabah özeti: hava durumu alınamadı: %s", e)
        return "🌡️ Hava durumuna ulaşamadım (internet?)."
    if not w:
        return None
    rain = w.get("rain")
    line = (f"{w['icon']} **{w['place']}:** şu an {w['temp']}, {w['words']}; gün içinde en yüksek {w['max']}, "
            f"en düşük {w['min']}" + (f", yağış ihtimali %{rain}" if rain is not None else "") + ".")
    if rain is not None and rain >= 50:
        line += " ☂️ Şemsiye almanı öneririm."
    return line


def _agenda(owner: str, now: datetime) -> list[str]:
    today = now.date()
    items = []  # (sort key, line)
    who = None if owner == db.ALL else owner
    for r in db.list_reminders(owner):
        due = datetime.strptime(r["due_at"], "%Y-%m-%d %H:%M:%S")
        if r["kind"] != "timer" and due.date() == today and (who is None or r.get("owner") == who):
            icon = "⏰" if r["kind"] == "alarm" else "🔔"
            items.append((due.strftime("%H:%M"), f"{icon} {due:%H:%M} {r['text'] or ('Alarm' if r['kind'] == 'alarm' else 'Hatırlatma')}"))
    if (owner == db.ALL or identity.is_admin()) and outlook.can_read():
        try:
            start = datetime.combine(today, datetime.min.time())
            for e in outlook.events(start, start + timedelta(days=1)):
                begin = datetime.strptime(e["due_at"], "%Y-%m-%d %H:%M:%S")
                when = "Tüm gün" if e.get("all_day") else begin.strftime("%H:%M")
                place = f" ({e['location']})" if e.get("location") else ""
                items.append(("00:00" if e.get("all_day") else when, f"📆 {when} {e['text']}{place}"))
        except Exception as e:
            log.warning("Sabah özeti: Outlook okunamadı: %s", e)
            items.append(("99", "⚠️ Outlook takvimini okuyamadım."))
    later = now.hour >= 12  # later in the day only what is still ahead
    if later:
        items = [(key, line) for key, line in items if key in ("00:00", "99") or key >= now.strftime("%H:%M")]
    if not items:
        return [f"📅 {'Günün geri kalanında' if later else 'Bugün'} takviminde ve hatırlatmalarında bir şey yok."]
    return [f"📅 **Bugün{' (kalanlar)' if later else ''}:**"] + [f"- {line}" for _, line in sorted(items)]


def _lists(owner: str) -> list[str]:
    lines = []
    for name, icon, title in (("alışveriş", "🛒", "Alışveriş listende"), ("yapılacaklar", "✅", "Yapılacaklar listende")):
        items = [i["text"] for i in db.list_notes(owner, name) if not i["done"]]
        if items:
            shown = ", ".join(items[:6]) + (f" ve {len(items) - 6} şey daha" if len(items) > 6 else "")
            lines.append(f"{icon} {title} {len(items)} şey var: {shown}.")
    return lines


def _news() -> list[str]:
    try:
        items = online.headlines("gündem")[:3]
    except Exception as e:
        log.warning("Sabah özeti: haberler alınamadı: %s", e)
        return []
    if not items:
        return []
    lines = ["📰 **Gündemden:**"]
    for i in items:
        title = i["title"].replace("[", "(").replace("]", ")")  # a "[" in the title would break the link
        lines.append(f"- [{title}]({i['link']})" if i.get("link") else f"- {title}")
    return lines


def build(owner: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    parts = [_greeting(owner, now)]
    if owner == identity.GUEST:
        parts.append("Kişisel özetin (hava, ajanda, listeler) için seni tanımam lazım: bir cümle söyle ya da şifreni yaz.")
        return "\n\n".join(parts)
    weather = _weather()
    if weather:
        parts.append(weather)
    elif not config.load().get("weather_city"):
        parts.append("🌡️ Hava durumunu da söylemem için Ayarlar → Bağlantılar'a şehrini yaz.")
    parts.append("\n".join(_agenda(owner, now)))
    lists = _lists(owner)
    if lists:
        parts.append("\n".join(lists))
    news = _news()
    if news:
        parts.append("\n".join(news))
    parts.append("İyi bir gün geçirmeni dilerim! 🌿" if now.hour < 18 else "İyi akşamlar! 🌙")
    return "\n\n".join(parts)
