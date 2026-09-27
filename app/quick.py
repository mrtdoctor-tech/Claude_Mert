"""Answers that come straight from the computer's clock instead of the model.

Small models (e.g. gemma3:1b) often misread the time even when it is given to them,
so simple "what time / what day is it" questions are answered here: always right and instant.
"""

import re
from datetime import datetime

DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

_END = r"(?![a-zçğıöşü])"  # "saat kaç" but not "saat kaçta"
_TIME = re.compile(
    r"\bsaat\s+(?:[şs]u\s*an(?:da)?\s+)?ka[çc]" + _END
    + r"|\b[şs]u\s*an(?:da)?\s+saat\s+ka[çc]" + _END
    + r"|\bwhat\s+time\s+is\s+it\b"
)
_DATE = re.compile(
    r"\bbug[üu]n\s+(?:ay[ıi]n\s+ka[çc][ıi]|g[üu]nlerden\s+ne|hangi\s+g[üu]n|ne\s+g[üu]n[üu]?)" + _END
    + r"|\b(?:bug[üu]n[üu]n\s+)?tarih(?:i)?\s+ne" + _END
    + r"|\bay[ıi]n\s+ka[çc][ıi]" + _END
    + r"|\bhangi\s+g[üu]ndeyiz\b"
    + r"|\bwhat(?:'s|\s+is)\s+the\s+date\b|\bwhat\s+day\s+is\s+it\b"
)
MAX_LENGTH = 60  # longer messages are real requests ("saat kaçta ... hesapla"), leave them to the model


def answer(text: str, now: datetime | None = None) -> str | None:
    if len(text) > MAX_LENGTH:
        return None
    lowered = text.casefold()
    wants_time, wants_date = bool(_TIME.search(lowered)), bool(_DATE.search(lowered))
    if not (wants_time or wants_date):
        return None
    now = now or datetime.now()
    parts = []
    if wants_date:
        parts.append(f"Bugün {now.day} {MONTHS_TR[now.month - 1]} {now.year}, {DAYS_TR[now.weekday()]}.")
    if wants_time:
        parts.append(f"Saat {now:%H:%M}.")
    return " ".join(parts)
