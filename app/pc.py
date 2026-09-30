"""Controlling programs on this Windows computer (3.6): Excel files, music (media keys), Spotify.

Everything happens on the computer itself: Excel through its COM automation interface (pywin32),
music through the keyboard's media keys, Spotify through its "spotify:" links.
Only recognised people may use it (guests may not open files; Spotify is an internet service).
"""

import logging
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import quote

from . import identity

log = logging.getLogger("asistan.pc")

MAX_LENGTH = 120
EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".csv"}
OPENABLE_EXTENSIONS = EXCEL_EXTENSIONS | {".docx", ".doc", ".pdf", ".pptx", ".ppt", ".txt"}
_SAVE = r"kayded|kaydet(?!me)"  # kaydet, kaydedip, kaydederek (but not kaydetmeden)
_NO_SAVE = r"kaydetme|kaydetmeyerek"
_FILE_WORD = r"\b(dosya|tablo)\w*"
SKIP_DIRS = {"appdata", "node_modules", ".git", "$recycle.bin", "windows", "program files"}
MAX_FILES_SCANNED = 30000


def _lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


def _words(text: str) -> list[str]:
    """Words without apostrophe suffixes: "Bütçe2026'yı" → "bütçe2026"."""
    return [re.sub(r"['’].*$", "", w) for w in re.findall(r"[\w'’]+", _lower(text))]


# COM (Excel/Outlook) needs initialising in every thread that uses it.

def com(fn):
    import pythoncom

    pythoncom.CoInitialize()
    try:
        return fn()
    finally:
        pythoncom.CoUninitialize()


def windows_only() -> str | None:
    return None if os.name == "nt" else "Bu özellik yalnızca Windows'ta çalışır."


# Excel

_EXCEL_WORDS = {"excel", "excelde", "exceli", "excelden", "dosya", "dosyası", "dosyasını", "dosyayı", "dosyamı",
                "tablo", "tablosu", "tablosunu", "tabloyu", "aç", "açar", "açarmısın", "açabilir", "misin", "mısın",
                "kapat", "kapatır", "kapatabilir", "kaydet", "kaydederek", "kaydetmeden", "kaydetme", "kaydedip",
                "ve", "bana", "lütfen", "adlı", "isimli", "şu", "bu", "benim", "da", "de", "ile", "hepsini", "tüm",
                "bütün", "dosyaları", "dosyalarını", "açık", "olan", "programını", "programı", "uygulamasını"}


def _excel_query(text: str) -> str:
    return " ".join(w for w in _words(text) if w not in _EXCEL_WORDS)


def _search_roots() -> list[Path]:
    home = Path(os.environ.get("USERPROFILE", Path.home()))
    roots = [home / "Desktop", home / "Documents", home / "Downloads"]
    # Google Drive (3.28: the HourGlow files are there): "My Drive (e-mail)" in the user folder, or drive G:
    roots += [*home.glob("My Drive*"), *home.glob("Google Drive*"), Path("G:/My Drive"), Path("G:/Drive'ım")]
    for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if os.environ.get(key):
            roots.append(Path(os.environ[key]))
    seen, result = set(), []
    for r in roots:
        if r.exists() and str(r).lower() not in seen:
            seen.add(str(r).lower())
            result.append(r)
    return result


def find_file(query: str, extensions=EXCEL_EXTENSIONS, roots: list[Path] | None = None) -> list[Path]:
    """Files whose name contains every word of the query, best first (exact name, then most recently changed)."""
    wanted = _words(query)
    if not wanted:
        return []
    matches = []
    for root in roots or _search_roots():
        scanned = 0  # per place: a big OneDrive must not use up the search before Google Drive
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in SKIP_DIRS]
            for name in files:
                scanned += 1
                path = Path(folder) / name
                if path.suffix.lower() not in extensions or name.startswith("~$"):
                    continue
                stem = _lower(path.stem)
                joined = re.sub(r"[\s_.-]+", "", stem)  # "HourGlow_Takip" also matches "hour glow takip"
                if all(w in stem or w in joined for w in wanted) or "".join(wanted) in joined:
                    matches.append(path)
            if scanned > MAX_FILES_SCANNED:
                break
    exact = " ".join(wanted)

    def rank(p: Path):
        stem = " ".join(_words(p.stem))
        try:
            changed = p.stat().st_mtime
        except OSError:
            changed = 0
        return (stem != exact, -changed)

    return sorted(set(matches), key=rank)


def _running_excel():
    import win32com.client

    try:
        return win32com.client.GetActiveObject("Excel.Application")
    except Exception:
        return None


def _open_books(excel) -> list:
    return [excel.Workbooks.Item(i) for i in range(1, excel.Workbooks.Count + 1)]


def _excel_close(query: str, save: bool | None) -> str:
    excel = _running_excel()
    if excel is None:
        return "Excel şu anda açık değil."
    books = _open_books(excel)
    if query:
        books = [b for b in books if all(w in _lower(b.Name) for w in _words(query))]
        if not books:
            return f"Açık Excel dosyaları arasında \"{query}\" bulamadım."
    if save is None:
        # No choice given: let Excel ask about unsaved changes itself.
        names = ", ".join(b.Name for b in books)
        threading.Thread(target=com, args=(lambda: _close_asking(query),), daemon=True).start()
        return f"Kapatıyorum: {names}. Kaydedilmemiş değişiklik varsa Excel sana soracak."
    closed, skipped = [], []
    excel.DisplayAlerts = False
    try:
        for b in books:
            if save and not b.Path:
                skipped.append(b.Name)  # never saved: it has no file name, "Save" would open a dialog
                continue
            b.Close(SaveChanges=bool(save))
            closed.append(b.Name)
    finally:
        excel.DisplayAlerts = True
    if excel.Workbooks.Count == 0:
        excel.Quit()
    reply = f"{'Kaydedip kapattım' if save else 'Kaydetmeden kapattım'}: {', '.join(closed) or '-'}."
    if skipped:
        reply += (f" {', '.join(skipped)} hiç kaydedilmemiş (dosya adı yok), onu açık bıraktım; "
                  "Excel'de Dosya > Farklı Kaydet ile kaydedebilirsin.")
    return reply


def _close_asking(query: str):
    excel = _running_excel()
    if excel is None:
        return
    books = _open_books(excel)
    if query:
        for b in books:
            if all(w in _lower(b.Name) for w in _words(query)):
                b.Close()
    else:
        excel.Quit()


def _excel_save(query: str) -> str:
    excel = _running_excel()
    if excel is None:
        return "Excel şu anda açık değil."
    books = _open_books(excel)
    if query:
        books = [b for b in books if all(w in _lower(b.Name) for w in _words(query))]
    if not books:
        return "Kaydedilecek açık bir Excel dosyası bulamadım."
    saved, skipped = [], []
    for b in books:
        if not b.Path:
            skipped.append(b.Name)
            continue
        b.Save()
        saved.append(b.Name)
    reply = f"Kaydettim: {', '.join(saved)}." if saved else ""
    if skipped:
        reply += f" {', '.join(skipped)} hiç kaydedilmemiş; Excel'de Dosya > Farklı Kaydet ile bir ad ver."
    return reply.strip()


def _excel_list() -> str:
    excel = _running_excel()
    if excel is None or excel.Workbooks.Count == 0:
        return "Açık bir Excel dosyası yok."
    return "Açık Excel dosyaları: " + ", ".join(b.Name for b in _open_books(excel)) + "."


def _excel_open(query: str, excel_only: bool = True) -> str:
    if not query:
        os.startfile("excel.exe")
        return "Excel'i açıyorum."
    found = find_file(query, EXCEL_EXTENSIONS if excel_only else OPENABLE_EXTENSIONS)
    if not found:
        places = ", ".join(p.name for p in _search_roots())
        kind = "Excel dosyası" if excel_only else "dosya"
        return f"\"{query}\" adında bir {kind} bulamadım (baktığım yerler: {places})."
    os.startfile(str(found[0]))
    more = f" (Bu adla {len(found) - 1} dosya daha var; en uygun olanı açtım.)" if len(found) > 1 else ""
    return f"Açıyorum: {found[0].name}{more}"


def _excel(text: str) -> str | None:
    """"Excel'i aç", "bütçe dosyasını Excel'de aç", "Excel'i kaydetmeden kapat", "bütçe dosyasını kaydet"...

    Without the word Excel only "<name> dosyasını aç/kapat/kaydet" counts; opening then also finds Word/PDF files.
    """
    low = _lower(text)
    excel = bool(re.search(r"\bexcel", low))
    if not excel and not re.search(_FILE_WORD, low):
        return None
    query = _excel_query(text)
    if re.search(r"açık\s+(excel\s+)?(dosya|tablo)|hangi\s+dosyalar\s+açık", low):
        return com(_excel_list)
    if re.search(r"kapat", low):
        save = False if re.search(_NO_SAVE, low) else True if re.search(_SAVE, low) else None
        return com(lambda: _excel_close(query, save))
    if re.search(_SAVE, low) and not re.search(_NO_SAVE, low):
        return com(lambda: _excel_save(query))
    if re.search(r"\baç", low):
        return _excel_open(query, excel_only=excel)
    return None


# Music: the keyboard's media keys work with Spotify, YouTube in the browser, Windows Media Player...

_VK = {"toggle": 0xB3, "next": 0xB0, "prev": 0xB1, "up": 0xAF, "down": 0xAE, "mute": 0xAD}
_APPCOMMAND = {"toggle": 14, "next": 11, "prev": 12}  # APPCOMMAND_MEDIA_PLAY_PAUSE, _NEXTTRACK, _PREVIOUSTRACK
_MEDIA = [
    (re.compile(r"sonraki\s+şarkı|sıradaki\s+şarkı|şarkıyı\s+(geç|atla|değiştir)|diğer\s+şarkı"), "next", 1,
     "Sonraki şarkıya geçtim."),
    (re.compile(r"önceki\s+şarkı|bir\s+önceki|geri\s+(al|dön)\s+şarkı"), "prev", 1, "Önceki şarkıya döndüm."),
    (re.compile(r"(müziği|müzik|şarkıyı|spotify'?ı?)\s*(durdur|duraklat|kes|kapat)|müzik\s+dursun"), "pause", 1,
     "Müziği durdurdum."),
    (re.compile(r"(müziğe|müziği|şarkıya|çalmaya)\s+devam|müziği\s+(başlat|devam\s+ettir|aç)"), "play", 1,
     "Müziğe devam ediyorum."),
    (re.compile(r"sesi\s+(aç|yükselt|artır|arttır)|sesi\s+biraz\s+aç"), "up", 5, "Sesi açtım."),
    (re.compile(r"sesi\s+(kıs|azalt|düşür)|sesi\s+biraz\s+kıs"), "down", 5, "Sesi kıstım."),
    (re.compile(r"sesi\s+(kapat|sustur)|sessize\s+al"), "mute", 1, "Sesi kapattım (tekrar söylersen açarım)."),
]
_IDLE_TITLES = {"spotify", "spotify free", "spotify premium", ""}  # Spotify's window title when nothing plays


def _press(key: str, times: int = 1):
    """The keyboard's media keys. They are "extended" keys: without that flag some programs ignore them."""
    import ctypes

    for _ in range(times):
        ctypes.windll.user32.keybd_event(_VK[key], 0, 1, 0)  # KEYEVENTF_EXTENDEDKEY
        ctypes.windll.user32.keybd_event(_VK[key], 0, 3, 0)  # + KEYEVENTF_KEYUP
        time.sleep(0.03)


def _spotify_window():
    """(window, title) of the Spotify desktop app, or None. The title is "Artist - Song" while music plays."""
    import ctypes
    from ctypes import wintypes

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if not length and not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not process:
            return True
        try:
            path = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(size)) \
                    and path.value.lower().endswith("\\spotify.exe") and length:
                # Only the main window (a Chromium window) tells what plays; Spotify also owns helper windows
                # such as "GDI+ Window (Spotify.exe)" whose title means nothing.
                kind = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, kind, 256)
                if kind.value.startswith("Chrome_WidgetWin"):
                    title = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, title, length + 1)
                    found.append((hwnd, title.value))
        finally:
            kernel32.CloseHandle(process)
        return True

    user32.EnumWindows(visit, 0)
    if not found:
        return None
    # Of Spotify's Chromium windows the main one is visible or carries the song / "Spotify" title.
    found.sort(key=lambda w: (not user32.IsWindowVisible(w[0]), not _looks_like_player(w[1])))
    return found[0]


def _looks_like_player(title: str) -> bool:
    return title.strip().lower() in _IDLE_TITLES or " - " in title


def _spotify_command(hwnd, command: str):
    import ctypes

    ctypes.windll.user32.SendMessageW(hwnd, 0x0319, 0, _APPCOMMAND[command] << 16)  # WM_APPCOMMAND


def _media(text: str) -> str | None:
    low = _lower(text)
    if len(low) > 60:
        return None
    for pattern, key, times, reply in _MEDIA:
        if not pattern.search(low):
            continue
        if key in ("up", "down", "mute"):  # the computer's volume
            _press(key, times)
            return reply
        spotify = _spotify_window()
        if spotify:
            hwnd, title = spotify
            # "Artist - Song" = playing, "Spotify Free" = paused; anything else: unknown, just press the button.
            playing = True if " - " in title else False if title.strip().lower() in _IDLE_TITLES else None
            if key == "pause" and playing is False:
                return "Spotify'da çalan bir şey yok, müzik zaten durmuş."
            if key == "play" and playing is True:
                return f"Zaten çalıyor: {title}."
            _spotify_command(hwnd, "toggle" if key in ("pause", "play") else key)
            if key in ("next", "prev"):
                time.sleep(0.8)  # let Spotify show the new song in its title
                now = _spotify_window()
                if now and " - " in now[1]:
                    return f"{reply} Şimdi çalan: {now[1]}."
            return reply
        # No Spotify app: the media keys reach whatever plays (e.g. Spotify or YouTube in the browser).
        _press("toggle" if key in ("pause", "play") else key, times)
        return reply
    return None


# Spotify (without a Premium connection it can open the app and search, but not start a song by itself)

_SPOTIFY_WORDS = {"spotify", "spotifyda", "spotifydan", "spotifyı", "spotifyi", "çal", "çalar", "çalarmısın",
                  "çalabilir", "misin", "mısın", "aç", "açar", "bana", "lütfen", "şarkısını", "şarkısı", "şarkı",
                  "şarkıyı", "şarkılarını", "şarkıları", "dinlemek", "istiyorum", "dinlet", "biraz", "bir", "ve",
                  "müzik", "müziği", "den", "dan", "da", "de"}


def _spotify(text: str) -> str | None:
    low = _lower(text)
    if not re.search(r"spotify", low):
        return None
    query = " ".join(w for w in _words(text) if w not in _SPOTIFY_WORDS)
    if not query or not re.search(r"çal|dinle|ara\b|bul", low):
        os.startfile("spotify:")
        return "Spotify'ı açıyorum."
    os.startfile("spotify:search:" + quote(query))
    return (f"Spotify'da \"{query}\" aramasını açtım; çalmak için sonuçlardan birine bas. "
            "(Ücretsiz Spotify hesabında şarkıyı dışarıdan başlatmaya Spotify izin vermiyor.)")


# Entry point for the chat

def is_command(text: str) -> bool:
    low = _lower(text)
    if re.search(r"\b(nasıl|neden|niye|niçin|nedir|ne\s+demek|ne\s+işe|formül\w*)\b", low):
        return False  # a question about Excel ("pivot tablo nasıl açılır?") is for the model
    file_command = re.search(_FILE_WORD + r".*\b(aç|açar|kapat|kaydet|kayded)", low) and len(low) <= 80
    return len(low) <= MAX_LENGTH and bool(
        re.search(r"\bexcel|spotify", low) or file_command
        or (len(low) <= 60 and any(p.search(low) for p, *_ in _MEDIA)))


def handle(text: str, owner: str) -> str | None:
    """A reply for a computer command, or None if the message is something else. Runs in a worker thread."""
    if not is_command(text):
        return None
    if owner == identity.GUEST:
        return "Bilgisayardaki programları yalnızca tanıdığım kişiler kullanabilir. Bir cümle söyle ya da şifreni yaz."
    problem = windows_only()
    if problem:
        return problem
    try:
        return _excel(text) or _media(text) or _spotify(text)  # "Spotify'ı durdur" is a music command
    except ImportError:
        return "Excel kontrolü için gereken paket (pywin32) kurulu değil. baslat.bat'ı kapatıp yeniden aç."
    except Exception as e:
        log.exception("Bilgisayar komutu başarısız oldu")
        return f"Bunu yapamadım: {e}"

