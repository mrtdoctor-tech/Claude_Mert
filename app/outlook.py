"""Copying reminders into the Outlook calendar (3.6), so the phone shows them too.

It talks to the Outlook program on this computer (COM, like Excel), not to Microsoft's servers directly:
Outlook then syncs the appointment to the account (e.g. outlook.com) and from there to the phone.
No app registration or password is needed. It needs the classic Outlook desktop program; the "new Outlook"
has no COM interface.

Only the admin's reminders are copied (the Outlook account on this computer is the admin's), and only when
the admin turned it on in Settings. Timers are never copied.
"""

import locale
import logging
import os
import threading
import time
from datetime import datetime, timedelta

from . import config, db
from .pc import com, windows_only

log = logging.getLogger("asistan.outlook")

OL_APPOINTMENT = 1
RECURRENCE = {"daily": 0, "weekly": 1, "monthly": 2, "yearly": 5}  # olRecursDaily, ...Weekly, ...Monthly, ...Yearly


def classic_outlook_path() -> str | None:
    """Where the classic Outlook program is, or None.

    Asking Windows for "Outlook.Application" when classic Outlook is not really installed (e.g. a leftover Office 2016
    registration) starts the Office setup wizard, so the registered program file is checked first.
    """
    import winreg

    try:
        clsid = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, r"Outlook.Application\CLSID")
    except OSError:
        return None
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32", 0,
                                winreg.KEY_READ | view) as key:
                command = winreg.QueryValueEx(key, "")[0]
        except OSError:
            continue
        path = command.split('"')[1] if command.startswith('"') else command.split(" /")[0]
        path = os.path.expandvars(path.strip())
        if path.lower().endswith("outlook.exe") and os.path.exists(path):
            return path
    return None


def has_mail_profile() -> bool:
    """Classic Outlook without an account shows its "add an account" wizard when started; check for a profile first."""
    import winreg

    for version in ("16.0", "15.0"):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\Office\{version}\Outlook\Profiles") as key:
                if winreg.QueryInfoKey(key)[0] > 0:  # number of profiles
                    return True
        except OSError:
            continue
    return False


NO_PROFILE = ("Klasik Outlook kurulu ama içinde henüz hesap yok (bu yüzden açılınca \"hesap ekle\" sihirbazı çıkıyor). "
              "Başlat menüsünden \"Outlook (klasik)\" programını bir kez aç, e-posta hesabını ekle, sonra tekrar dene.")

NOT_INSTALLED = ("Bu bilgisayarda klasik Outlook programı kurulu görünmüyor (kayıtlı Outlook eksik ya da yarım kurulmuş; açılmaya "
                 "çalışılınca kurulum sihirbazı çıkıyor). \"Yeni Outlook\" ya da tarayıcıdaki Outlook bu bağlantıyı "
                 "desteklemiyor.")


def _admin_name() -> str | None:
    return next((s["name"] for s in db.list_speakers() if s["is_admin"]), None)


def will_sync(owner: str | None, kind: str) -> bool:
    if kind == "timer" or not config.load().get("outlook_sync") or windows_only():
        return False
    if not classic_outlook_path() or not has_mail_profile():
        return False
    return owner is None or owner == _admin_name()


def _outlook():
    import win32com.client

    return win32com.client.Dispatch("Outlook.Application")


def _create(reminder: dict) -> str:
    appt = _outlook().CreateItem(OL_APPOINTMENT)
    due = datetime.strptime(reminder["due_at"], "%Y-%m-%d %H:%M:%S")
    appt.Subject = reminder["text"] or ("Alarm" if reminder["kind"] == "alarm" else "Hatırlatma")
    appt.Body = "Yerel Asistan hatırlatması"
    appt.Start = due.strftime("%Y-%m-%d %H:%M")  # Outlook reads this as local time
    appt.Duration = 15
    appt.BusyStatus = 0  # free: a reminder should not block the calendar
    appt.ReminderSet = True
    appt.ReminderMinutesBeforeStart = 0
    if reminder.get("repeat") in RECURRENCE:
        pattern = appt.GetRecurrencePattern()
        pattern.RecurrenceType = RECURRENCE[reminder["repeat"]]
        pattern.NoEndDate = True
    appt.Save()
    return appt.EntryID


def _add(reminder_id: int):
    reminder = db.get_reminder(reminder_id)
    if not reminder:
        return
    try:
        entry = com(lambda: _create(reminder))
        db.set_reminder_calendar(reminder_id, entry, "")
        forget_events()
        log.info("Outlook takvimine eklendi: %s", reminder["text"])
    except Exception as e:
        log.warning("Outlook takvimine eklenemedi: %s", e)
        db.set_reminder_calendar(reminder_id, None, f"Outlook takvimine eklenemedi: {e}")


def _remove(entry_id: str):
    try:
        com(lambda: _outlook().GetNamespace("MAPI").GetItemFromID(entry_id).Delete())
        forget_events()
    except Exception as e:
        log.warning("Outlook takviminden silinemedi: %s", e)


def add_later(reminder_id: int):
    """Copy the reminder into Outlook in the background (Outlook may take a few seconds to start)."""
    threading.Thread(target=_add, args=(reminder_id,), daemon=True).start()


def remove_later(reminder: dict):
    if reminder.get("calendar_id"):
        threading.Thread(target=_remove, args=(reminder["calendar_id"],), daemon=True).start()


# Reading the Outlook calendar (3.10): shown read-only in the agenda, next to the assistant's own reminders.

EVENTS_CACHE_SECONDS = 60
MAX_EVENTS = 500
_events_cache: dict = {}  # (start, end) -> (time, events)


def can_read() -> bool:
    return bool(config.load().get("outlook_sync")) and not windows_only() and bool(classic_outlook_path()) \
        and has_mail_profile()


def _local(value) -> datetime:
    """pywin32 hands Outlook's local times over marked as UTC; they are local wall-clock times."""
    return datetime(value.year, value.month, value.day, value.hour, value.minute)


def _restriction(start: datetime, end: datetime, fmt: str) -> str:
    return f"[Start] < '{end.strftime(fmt)}' AND [End] > '{start.strftime(fmt)}'"


def _read(start: datetime, end: datetime) -> list[dict]:
    items = _outlook().GetNamespace("MAPI").GetDefaultFolder(9).Items  # olFolderCalendar
    items.IncludeRecurrences = True  # every occurrence of a repeating appointment as its own item
    items.Sort("[Start]")
    # Outlook wants dates in the Windows date format (e.g. 30.09.2026 in Turkish); try it, then the US form.
    try:
        locale.setlocale(locale.LC_TIME, "")
    except locale.Error:
        pass
    found = None
    for fmt in ("%x %H:%M", "%m/%d/%Y %I:%M %p", "%d.%m.%Y %H:%M"):
        try:
            found = items.Restrict(_restriction(start, end, fmt))
            break
        except Exception:
            continue
    if found is None:
        raise RuntimeError("Outlook tarih aralığını kabul etmedi")
    events = []
    item = found.GetFirst()
    while item is not None and len(events) < MAX_EVENTS:
        try:
            begin, finish = _local(item.Start), _local(item.End)
            if finish > start and begin < end:  # Restrict may be loose with some date formats
                events.append({
                    "id": f"o{len(events)}", "kind": "outlook", "text": item.Subject or "(konu yok)",
                    "due_at": begin.strftime("%Y-%m-%d %H:%M:%S"), "end_at": finish.strftime("%Y-%m-%d %H:%M:%S"),
                    "all_day": bool(item.AllDayEvent), "location": item.Location or "",
                    "repeat": None, "recurring": bool(item.IsRecurring),
                })
        except Exception as e:  # one odd item must not hide the others
            log.debug("Outlook kaydı okunamadı: %s", e)
        item = found.GetNext()
    return events


def events(start: datetime, end: datetime) -> list[dict]:
    """Outlook appointments between start and end, without the ones the assistant itself added."""
    key = (start, end)
    cached = _events_cache.get(key)
    if cached and time.time() - cached[0] < EVENTS_CACHE_SECONDS:
        return cached[1]
    found = com(lambda: _read(start, end))
    ours = {(r["text"], r["due_at"][:16]) for r in db.list_reminders() if r.get("calendar_id")}
    found = [e for e in found if (e["text"], e["due_at"][:16]) not in ours]
    _events_cache.clear()
    _events_cache[key] = (time.time(), found)
    return found


def forget_events():
    _events_cache.clear()


def test() -> str:
    """Check that Outlook answers; tells which account's calendar will be used."""
    problem = windows_only()
    if problem:
        return problem
    if not classic_outlook_path():
        return "⚠️ " + NOT_INSTALLED
    if not has_mail_profile():
        return "⚠️ " + NO_PROFILE

    def check():
        ns = _outlook().GetNamespace("MAPI")
        calendar = ns.GetDefaultFolder(9)  # olFolderCalendar
        store = calendar.Store.DisplayName if calendar.Store else ""
        return f"✅ Outlook çalışıyor. Hatırlatmalar şu takvime eklenecek: {calendar.Name} ({store})."

    try:
        return com(check)
    except ImportError:
        return "Gereken paket (pywin32) kurulu değil. baslat.bat'ı kapatıp yeniden aç."
    except Exception as e:
        return (f"⚠️ Outlook'a bağlanılamadı ({e}). Bilgisayarda klasik Outlook programı kurulu ve hesabın ekli olmalı; "
                "\"yeni Outlook\" bu bağlantıyı desteklemiyor.")
