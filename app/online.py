"""Weather and news from the internet (3.11). Never for guests (the user's rule: internet features are for
recognised people only).

Weather: Open-Meteo (free, no key, no account): only the city name / its coordinates are sent.
News: the public RSS feeds of news sites: only the feed address is requested.
Answers are put together here from the data (like the clock answers), not by the language model,
so numbers are never made up.
"""

import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx

from . import config, identity
from .quick import DAYS_TR, MONTHS_TR

log = logging.getLogger("asistan.online")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = httpx.Timeout(12.0, connect=6.0)
WEATHER_CACHE = 15 * 60
NEWS_CACHE = 10 * 60
MAX_LENGTH = 90
HEADLINES = 7

NEWS_FEEDS = {  # category -> [(source name, RSS/Atom address)]
    "gündem": [("NTV", "https://www.ntv.com.tr/gundem.rss"), ("BBC Türkçe", "https://feeds.bbci.co.uk/turkce/rss.xml")],
    "ekonomi": [("NTV", "https://www.ntv.com.tr/ekonomi.rss")],
    "spor": [("NTV", "https://www.ntv.com.tr/spor.rss")],
    "dünya": [("NTV", "https://www.ntv.com.tr/dunya.rss")],
    "teknoloji": [("NTV", "https://www.ntv.com.tr/teknoloji.rss")],
    "sağlık": [("NTV", "https://www.ntv.com.tr/saglik.rss")],
}

# WMO weather codes (used by Open-Meteo) in Turkish
WEATHER_CODES = {
    0: ("☀️", "açık"), 1: ("🌤️", "çoğunlukla açık"), 2: ("⛅", "parçalı bulutlu"), 3: ("☁️", "kapalı"),
    45: ("🌫️", "sisli"), 48: ("🌫️", "kırağılı sis"),
    51: ("🌦️", "hafif çisenti"), 53: ("🌦️", "çisenti"), 55: ("🌧️", "yoğun çisenti"),
    56: ("🌧️", "dondurucu çisenti"), 57: ("🌧️", "yoğun dondurucu çisenti"),
    61: ("🌦️", "hafif yağmurlu"), 63: ("🌧️", "yağmurlu"), 65: ("🌧️", "şiddetli yağmurlu"),
    66: ("🌧️", "dondurucu yağmur"), 67: ("🌧️", "şiddetli dondurucu yağmur"),
    71: ("🌨️", "hafif karlı"), 73: ("🌨️", "karlı"), 75: ("❄️", "yoğun karlı"), 77: ("🌨️", "kar taneli"),
    80: ("🌦️", "hafif sağanak"), 81: ("🌧️", "sağanak yağışlı"), 82: ("⛈️", "şiddetli sağanak"),
    85: ("🌨️", "hafif kar sağanağı"), 86: ("❄️", "yoğun kar sağanağı"),
    95: ("⛈️", "gök gürültülü fırtına"), 96: ("⛈️", "dolulu fırtına"), 99: ("⛈️", "şiddetli dolulu fırtına"),
}

_cache: dict = {}  # key -> (time, value)


def _lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


def _cached(key, seconds, make):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < seconds:
        return hit[1]
    value = make()
    _cache[key] = (time.time(), value)
    return value


def _get(url: str, **params):
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": "YerelAsistan/1.0"}) as client:
        response = client.get(url, params=params or None)
        response.raise_for_status()
        return response


# Weather

def _place(city: str) -> dict:
    data = _get(GEOCODE_URL, name=city, count=1, language="tr", format="json").json()
    results = data.get("results") or []
    if not results:
        raise LookupError(f"\"{city}\" adında bir yer bulamadım.")
    return results[0]


def forecast(city: str) -> dict:
    def make():
        place = _place(city)
        data = _get(FORECAST_URL, latitude=place["latitude"], longitude=place["longitude"], timezone="auto",
                    forecast_days=7,
                    current="temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
                    daily="weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max").json()
        return {"place": place.get("name") or city, "current": data.get("current") or {}, "daily": data.get("daily") or {}}

    return _cached(("weather", _lower(city)), WEATHER_CACHE, make)


def _describe(code) -> tuple[str, str]:
    return WEATHER_CODES.get(int(code) if code is not None else -1, ("🌡️", "bilinmeyen hava"))


def _deg(value) -> str:
    return f"{round(value)}°C" if value is not None else "?"


def _day_line(daily: dict, i: int, label: str) -> str:
    icon, words = _describe(daily["weather_code"][i])
    rain = daily.get("precipitation_probability_max", [None] * (i + 1))[i]
    rain_text = f", yağış ihtimali %{rain}" if rain is not None else ""
    return (f"{icon} {label}: {words}, en yüksek {_deg(daily['temperature_2m_max'][i])}, "
            f"en düşük {_deg(daily['temperature_2m_min'][i])}{rain_text}.")


def _day_label(day: date, today: date) -> str:
    if day == today:
        return "Bugün"
    if day == today + timedelta(days=1):
        return "Yarın"
    return f"{day.day} {MONTHS_TR[day.month - 1]} {DAYS_TR[day.weekday()]}"


_WEEKDAYS = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]


def _wanted_days(low: str, days: list[date]) -> list[int]:
    today = days[0]
    if re.search(r"\b(bu\s+hafta|haftalık|önümüzdeki\s+günler|hafta\s+boyunca|7\s+gün)", low):
        return list(range(len(days)))
    if re.search(r"hafta\s*sonu", low):
        return [i for i, d in enumerate(days) if d.weekday() >= 5][:2] or [0]
    if re.search(r"\byarından\s+sonra|öbür\s+gün", low):
        return [2] if len(days) > 2 else [0]
    if re.search(r"\byarın", low):
        return [1] if len(days) > 1 else [0]
    for n, name in enumerate(_WEEKDAYS):
        if re.search(rf"\b{name}", low):
            return [i for i, d in enumerate(days) if d.weekday() == n and d != today][:1] or [0]
    return [0]


_CITY = re.compile(r"([A-Za-zÇĞİÖŞÜçğıöşü]+)['’]?(?:da|de|ta|te|daki|deki)\s+(?:yarın\s+|bugün\s+|bu\s+hafta\s+)?hava")
_NOT_CITIES = {"burada", "orada", "şurada", "bugün", "yarın", "evde", "dışarıda", "sonra", "hafta", "haftada",
               "sabahta", "akşamda", "gece", "şuanda", "şu", "anda", "saatte", "günde", "ayda", "dışarda", "içeride"}


def weather_reply(text: str) -> str:
    low = _lower(text)
    match = _CITY.search(text)
    word = _lower(re.sub(r"['’]", "", text[match.start():].split()[0])) if match else ""  # the whole word, "hafta"
    is_place = match and word not in _NOT_CITIES and _lower(match.group(1)) not in _NOT_CITIES
    city = match.group(1) if is_place else config.load().get("weather_city", "")
    if not city:
        return ("Hangi şehrin havasına bakayım? \"İstanbul'da hava nasıl?\" diye sorabilirsin. Şehrini her seferinde "
                "söylememek için Ayarlar'da \"Hava durumu için şehir\" kısmına yaz.")
    try:
        f = forecast(city)
    except LookupError as e:
        return str(e)
    except Exception as e:
        log.warning("Hava durumu alınamadı: %s", e)
        return f"Hava durumu bilgisine ulaşamadım (internet bağlantısı?): {e}"
    daily, current = f["daily"], f["current"]
    days = [date.fromisoformat(d) for d in daily.get("time", [])]
    if not days:
        return "Hava durumu bilgisi boş geldi."
    wanted = _wanted_days(low, days)
    lines = [f"**{f['place']}**"]
    if wanted == [0] and current:
        icon, words = _describe(current.get("weather_code"))
        feels = current.get("apparent_temperature")
        lines.append(f"{icon} Şu an {_deg(current.get('temperature_2m'))}, {words}"
                     + (f" (hissedilen {_deg(feels)})" if feels is not None else "")
                     + (f", rüzgâr {round(current['wind_speed_10m'])} km/sa" if current.get("wind_speed_10m") is not None
                        else "") + ".")
    for i in wanted:
        lines.append(_day_line(daily, i, _day_label(days[i], days[0])))
    if re.search(r"yağmur|şemsiye|yağış", low):
        rain = daily.get("precipitation_probability_max", [None] * (wanted[0] + 1))[wanted[0]]
        if rain is not None:
            lines.append("☂️ Şemsiye almanı öneririm." if rain >= 50 else "Şemsiyeye muhtemelen gerek yok.")
    return "\n".join(lines)


def weather_summary() -> dict | None:
    """Short weather line for the agenda panel (the settings' city), or None."""
    city = config.load().get("weather_city", "")
    if not city:
        return None
    f = forecast(city)
    current, daily = f["current"], f["daily"]
    icon, words = _describe(current.get("weather_code"))
    return {"place": f["place"], "icon": icon, "words": words, "temp": _deg(current.get("temperature_2m")),
            "max": _deg((daily.get("temperature_2m_max") or [None])[0]),
            "min": _deg((daily.get("temperature_2m_min") or [None])[0]),
            "rain": (daily.get("precipitation_probability_max") or [None])[0]}


# News

_ATOM = "{http://www.w3.org/2005/Atom}"


def _parse_feed(xml_text: str, source: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.iter("item"):  # RSS 2.0
        when = item.findtext("pubDate") or ""
        try:
            stamp = parsedate_to_datetime(when).astimezone() if when else None
        except (TypeError, ValueError):
            stamp = None
        items.append({"title": (item.findtext("title") or "").strip(), "link": (item.findtext("link") or "").strip(),
                      "time": stamp, "source": source})
    for entry in root.iter(f"{_ATOM}entry"):  # Atom
        link = entry.find(f"{_ATOM}link")
        when = entry.findtext(f"{_ATOM}published") or entry.findtext(f"{_ATOM}updated") or ""
        try:
            stamp = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone() if when else None
        except ValueError:
            stamp = None
        items.append({"title": (entry.findtext(f"{_ATOM}title") or "").strip(),
                      "link": link.get("href", "") if link is not None else "", "time": stamp, "source": source})
    return [i for i in items if i["title"]]


def headlines(category: str) -> list[dict]:
    def make():
        found, errors = [], []
        for source, url in NEWS_FEEDS[category]:
            try:
                found += _parse_feed(_get(url).text, source)
            except Exception as e:
                errors.append(f"{source}: {e}")
                log.warning("Haber akışı okunamadı (%s): %s", url, e)
        if not found and errors:
            raise RuntimeError("; ".join(errors))
        epoch = datetime.min.replace(tzinfo=datetime.now().astimezone().tzinfo)
        found.sort(key=lambda i: i["time"] or epoch, reverse=True)
        seen, unique = set(), []
        for item in found:  # the same story from two sources
            key = _lower(item["title"])[:60]
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    return _cached(("news", category), NEWS_CACHE, make)


def news_reply(text: str) -> str:
    low = _lower(text)
    category = next((c for c in NEWS_FEEDS if c != "gündem" and re.search(rf"\b{c[:4]}", low)), "gündem")
    try:
        items = headlines(category)[:HEADLINES]
    except Exception as e:
        return f"Haberlere ulaşamadım (internet bağlantısı?): {e}"
    if not items:
        return "Şu an haber bulamadım."
    title = "Son haberler" if category == "gündem" else f"Son {category} haberleri"
    lines = [f"**📰 {title}**"]
    for item in items:
        stamp = f" · {item['time']:%H:%M}" if item["time"] and item["time"].date() == date.today() else ""
        name = item["title"].replace("[", "(").replace("]", ")")
        lines.append(f"- [{name}]({item['link']}) — {item['source']}{stamp}" if item["link"]
                     else f"- {name} — {item['source']}{stamp}")
    return "\n".join(lines)


# Chat entry point

_WEATHER = re.compile(
    r"\bhava\s*durumu|\bhava\b.{0,25}\b(nasıl|kaç\s+derece|ne\s+olacak|ne\s+durumda|soğuk|sıcak|yağmur|güzel\s+mi)"
    r"|\bkaç\s+derece|\byağmur\s+(yağacak|var|yağar)|\bşemsiye\s+(almalı|gerek|alayım)|\bkar\s+yağacak")
_NEWS = re.compile(r"\bhaber(ler|leri)?\b|\bgündem|\bmanşet")
_QUESTION_ABOUT = re.compile(r"\bnedir\b|\bne\s+demek|\bnasıl\s+(oluşur|olur)\b|\bneden\b")


def kind(text: str) -> str | None:
    low = _lower(text)
    if len(low) > MAX_LENGTH or _QUESTION_ABOUT.search(low):
        return None
    if _WEATHER.search(low):
        return "weather"
    if _NEWS.search(low) and not re.search(r"\bhaber\s+ver", low):  # "haber ver" is a reminder word
        return "news"
    return None


def is_command(text: str) -> bool:
    return kind(text) is not None


def handle(text: str, owner: str) -> str | None:
    what = kind(text)
    if not what:
        return None
    if owner == identity.GUEST:
        return ("İnternet gerektiren özellikler (hava durumu, haberler) yalnızca tanıdığım kişilere açık. "
                "Bir cümle söyle ya da şifreni yaz.")
    return weather_reply(text) if what == "weather" else news_reply(text)
