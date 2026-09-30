"""Local web server: serves the UI and the chat/memory/voice API."""

import asyncio
import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, identity, llm, memory, online, outlook, pc, presence, quick, reminders, stt, tts, voiceid

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("asistan")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
HISTORY_LIMIT = 30  # at least this many previous messages of the conversation are sent to the model
HISTORY_STEP = 10  # the window's start moves in steps, so the model's cached reading stays valid in between

app = FastAPI(title="Yerel Asistan")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def _no_stale_ui(request, call_next):
    # Make the browser re-check the UI files every time, so an update is never hidden by its cache.
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response
db.init()


@app.on_event("startup")
async def _catch_up_memory():
    log.info("Yerel Asistan sürüm %s hazır", config.VERSION)
    # Learn from messages that were not scanned before the app was last closed.
    identity.restore()  # the app restarted by itself (update, OneDrive): keep the person who was talking
    memory.init_cursor()
    memory.schedule(config.load())
    other = presence.other_computer()
    if other:
        log.warning("DİKKAT: Asistan şu anda %s bilgisayarında da açık görünüyor.", other)
    _presence_task = asyncio.create_task(presence.keep_marking())
    _background.add(_presence_task)
    _background.add(asyncio.create_task(reminders.run()))  # fires alarms, timers and reminders


_background: set = set()  # keeps background tasks referenced
_last_reply = {"text": "", "at": 0.0}  # what the assistant said last (spoken aloud), to recognise its own echo


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.replace("I", "ı").replace("İ", "i").lower()) if len(w) > 2}


def _is_echo(heard: str) -> bool:
    """The microphone picked up the assistant's own spoken reply (speakers, sesli sohbet), not a person."""
    if time.time() - _last_reply["at"] > 120:
        return False
    words = _words(heard)
    return len(words) >= 2 and len(words & _words(_last_reply["text"])) / len(words) >= 0.6


@app.on_event("shutdown")
async def _goodbye():
    presence.clear()


def _line(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


@app.get("/")
def index():
    # The version goes into the asset URLs too, so every update loads fresh CSS/JS.
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html.replace("{{VERSION}}", config.VERSION))


@app.get("/api/help")
def help_page():
    """NELER_YAPABILIR.md: what the assistant can do, with example commands."""
    path = STATIC_DIR.parent / "NELER_YAPABILIR.md"
    return {"markdown": path.read_text(encoding="utf-8") if path.exists() else ""}


@app.get("/api/version")
def version():
    return {
        "version": config.VERSION,
        "other_computer": presence.other_computer(),
        "stt_device": stt.current_device(),
        "identity": identity.state(),
    }


def _require_admin():
    if not identity.is_admin():
        raise HTTPException(403, "Bunu yalnızca yönetici (sesiyle tanınmış) yapabilir.")


def _own_conversation(conversation_id: int):
    """The conversation, if the person talking now may see it."""
    conv = db.get_conversation(conversation_id)
    who = identity.owner()
    if not conv or (who != db.ALL and conv.get("owner") != who):
        raise HTTPException(404, "Sohbet bulunamadı")
    return conv


# Settings

class SettingsIn(BaseModel):
    assistant_name: str | None = None
    model: str | None = None
    whisper_model: str | None = None
    language: str | None = None
    tts_voice: str | None = None
    auto_listen: bool | None = None
    memory_model: str | None = None
    whisper_device: str | None = None
    outlook_sync: bool | None = None
    weather_city: str | None = None
    mic_gain: float | None = None
    mic_calibrated: bool | None = None


@app.get("/api/settings")
def get_settings():
    return config.load()


@app.put("/api/settings")
def put_settings(body: SettingsIn):
    _require_admin()
    return config.save(body.model_dump())


@app.get("/api/models")
async def models():
    try:
        return {"models": await llm.list_models()}
    except llm.OllamaError as e:
        raise HTTPException(503, str(e))


# Conversations

@app.get("/api/conversations")
def conversations():
    return db.list_conversations(identity.owner())


@app.get("/api/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int):
    _own_conversation(conversation_id)
    return db.list_messages(conversation_id)


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: int):
    _own_conversation(conversation_id)
    db.delete_conversation(conversation_id)
    return {"ok": True}


class ChatIn(BaseModel):
    message: str
    conversation_id: int | None = None
    via: str = "yazı"  # "yazı" (typed) or "ses" (spoken), for the security log


def _notice_stream(text: str):
    """A reply that is not a conversation message (lock/switch notices): shown, never stored."""
    async def stream():
        yield _line({"type": "meta", "conversation_id": None, "instant": True, "notice": True,
                     "identity": identity.state()})
        yield _line({"type": "token", "text": text})
        yield _line({"type": "done"})
    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.post("/api/chat")
async def chat(body: ChatIn):
    text = body.message.strip()
    if not text:
        raise HTTPException(400, "Mesaj boş olamaz")

    notice = identity.handle_code(text)  # "1234" locks, "<Ad>1234" lets the admin switch sessions
    if notice:
        return _notice_stream(notice)

    identity.touch()
    who = identity.owner()
    speaker = None if who == db.ALL else who
    if who == identity.GUEST:
        db.log_security(f"Misafir mesajı ({body.via})", text)

    conversation_id = body.conversation_id
    conv = db.get_conversation(conversation_id) if conversation_id else None
    if conv is None or (who != db.ALL and conv.get("owner") != who):
        title = text if len(text) <= 50 else text[:47].rstrip() + "..."
        conversation_id = db.create_conversation(title, speaker)

    memory.cancel()  # free the CPU for the reply
    history = db.list_messages(conversation_id)
    start = max(0, len(history) - HISTORY_LIMIT)
    history = history[start - start % HISTORY_STEP:]
    db.add_message(conversation_id, "user", text, speaker)

    settings = config.load()
    messages = [{"role": "system", "content": memory.system_prompt_for(conversation_id, settings, who)}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": text + memory.clock_note()})  # the note is not saved
    # "saat kaç?" comes from the clock, "20 dakikalık sayaç kur" is set by rules: not by the model
    instant = quick.answer(text) or reminders.handle(text, who)
    if not instant and pc.is_command(text):  # Excel, music, Spotify on this computer
        instant = await run_in_threadpool(pc.handle, text, who)
    if not instant and online.is_command(text):  # weather and news from the internet (never for guests)
        instant = await run_in_threadpool(online.handle, text, who)

    async def from_clock():
        yield instant

    async def stream():
        yield _line({"type": "meta", "conversation_id": conversation_id, "instant": bool(instant),
                     "identity": identity.state()})
        parts = []
        try:
            source = from_clock() if instant else llm.chat_stream(settings["model"], messages)
            async for piece in source:
                parts.append(piece)
                yield _line({"type": "token", "text": piece})
        except llm.OllamaError as e:
            yield _line({"type": "error", "message": str(e)})
            return
        finally:
            memory.schedule(settings)
        reply = memory.strip_clock_echo("".join(parts))
        _last_reply.update(text=reply, at=time.time())
        if reply:
            db.add_message(conversation_id, "assistant", reply)
        yield _line({"type": "done"})

    return StreamingResponse(stream(), media_type="application/x-ndjson")


# Reminders, alarms, timers

class ReminderIn(BaseModel):
    text: str = ""
    due_at: str  # "YYYY-MM-DDTHH:MM" from the page's date-time field
    repeat: str | None = None


def _reminder_owner() -> str | None:
    who = identity.owner()
    if who == identity.GUEST:
        raise HTTPException(403, "Hatırlatıcılar kişiye özel; misafir modunda kullanılamaz.")
    return None if who == db.ALL else who


def _reminder_view(r: dict) -> dict:
    return {"id": r["id"], "kind": r["kind"], "text": reminders.label(r), "due_at": r["due_at"],
            "repeat": r["repeat"], "when": reminders.when_text(reminders._dt(r["due_at"])),
            "calendar": bool(r.get("calendar_id")), "calendar_note": r.get("calendar_note") or ""}


@app.get("/api/reminders")
def list_reminders():
    who = identity.owner()
    return [] if who == identity.GUEST else [_reminder_view(r) for r in db.list_reminders(who)]


@app.post("/api/reminders")
def add_reminder(body: ReminderIn):
    owner = _reminder_owner()
    try:
        due = datetime.fromisoformat(body.due_at)
    except ValueError:
        raise HTTPException(400, "Tarih/saat anlaşılamadı.")
    if due <= datetime.now() and not body.repeat:
        raise HTTPException(400, "Bu zaman geçmişte kaldı.")
    repeat = body.repeat if body.repeat in reminders.REPEAT_TR else None
    new_id = db.add_reminder(owner, "reminder", body.text.strip(), due.strftime("%Y-%m-%d %H:%M:00"), repeat)
    if outlook.will_sync(owner, "reminder"):
        outlook.add_later(new_id)
    return {"ok": True}


@app.delete("/api/reminders/{reminder_id}")
def cancel_reminder(reminder_id: int):
    owner, item = _reminder_owner(), db.get_reminder(reminder_id)
    if not item or (identity.owner() != db.ALL and item["owner"] != owner):
        raise HTTPException(404, "Hatırlatma bulunamadı")
    db.set_reminder_status(reminder_id, "cancelled")
    outlook.remove_later(item)
    return {"ok": True}


@app.get("/api/outlook/events")
async def outlook_events(start: str, end: str):
    """The admin's Outlook appointments for the agenda (read-only). Empty for everyone else."""
    who = identity.owner()
    if who == identity.GUEST or (who != db.ALL and not identity.is_admin()) or not outlook.can_read():
        return {"events": [], "available": False}
    try:
        begin, finish = datetime.fromisoformat(start), datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(400, "Tarih anlaşılamadı")
    if (finish - begin).days > 120:
        raise HTTPException(400, "Aralık çok uzun")
    try:
        found = await run_in_threadpool(outlook.events, begin, finish)
    except Exception as e:
        log.warning("Outlook takvimi okunamadı: %s", e)
        return {"events": [], "available": True, "error": f"Outlook takvimi okunamadı: {e}"}
    return {"events": found, "available": True}


@app.get("/api/weather")
async def weather():
    """Short weather line for the agenda. Internet feature: never for guests."""
    if identity.owner() == identity.GUEST:
        return {"weather": None}
    try:
        return {"weather": await run_in_threadpool(online.weather_summary)}
    except Exception as e:
        log.warning("Hava durumu alınamadı: %s", e)
        return {"weather": None, "error": str(e)}


@app.post("/api/outlook/test")
async def outlook_test():
    _require_admin()
    return {"message": await run_in_threadpool(outlook.test)}


@app.get("/api/alerts")
def alerts():
    """Polled by the page every few seconds: alerts to ring now, and the current person's running timers."""
    reminders.page_polled()
    now = datetime.now()
    ringing = []
    for a in db.list_alerts():
        late = (datetime.strptime(a["fired_at"], "%Y-%m-%d %H:%M:%S")
                - reminders._dt(a["due_at"])).total_seconds() > reminders.MISSED_AFTER
        ringing.append({"id": a["id"], "kind": a["kind"], "text": reminders.visible_text(a),
                        "due": reminders.when_text(reminders._dt(a["due_at"]), now), "missed": late})
    who = identity.owner()
    timers = [] if who == identity.GUEST else [
        {"id": r["id"], "text": reminders.label(r), "left": (reminders._dt(r["due_at"]) - now).total_seconds()}
        for r in db.list_reminders(who) if r["kind"] == "timer"]
    return {"alerts": ringing, "timers": timers}


@app.post("/api/alerts/{alert_id}/ack")
def ack_alert(alert_id: int):
    db.ack_alert(alert_id)
    return {"ok": True}


# Memories

class MemoryIn(BaseModel):
    content: str


@app.get("/api/memories")
def memories():
    who = identity.owner()
    return [] if who == identity.GUEST else db.list_memories(who)


@app.post("/api/memories")
def add_memory(body: MemoryIn):
    content = body.content.strip()
    if not content:
        raise HTTPException(400, "Boş bilgi eklenemez")
    who = identity.owner()
    if who == identity.GUEST:
        raise HTTPException(403, "Misafir modunda hafızaya bilgi eklenemez.")
    return {"id": db.add_memory(content, None if who == db.ALL else who)}


@app.post("/api/memories/learn")
async def learn_memories():
    """Scan not-yet-processed messages right away (used when the memory panel opens)."""
    try:
        added = await memory.learn_now(config.load())
    except llm.OllamaError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        log.exception("Hafıza çıkarımı başarısız oldu")
        raise HTTPException(500, f"Bilgiler çıkarılamadı: {e}")
    return {"added": added}


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int):
    item, who = db.get_memory(memory_id), identity.owner()
    if not item or (who != db.ALL and item.get("owner") != who):
        raise HTTPException(404, "Bilgi bulunamadı")
    db.delete_memory(memory_id)
    return {"ok": True}


# Voice

@app.post("/api/transcribe/warmup")
async def transcribe_warmup():
    """Load the speech model while the user is still talking."""
    settings = config.load()
    memory.schedule(settings)  # restart the idle countdown (it must never be dropped)
    try:
        await run_in_threadpool(stt.load, settings["whisper_model"], settings["whisper_device"])
        if identity.active():
            await run_in_threadpool(voiceid.warm_up)
    except Exception as e:
        log.warning("Ses modeli yüklenemedi: %s", e)
    return {"ok": True}


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    settings = config.load()
    memory.schedule(settings)
    suffix = Path(audio.filename or "").suffix or ".webm"
    # delete=False + manual cleanup: Windows cannot reopen a file that is still open.
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await audio.read())
        path = tmp.name
    try:
        text, device = await run_in_threadpool(
            stt.transcribe, path, settings["whisper_model"], settings["language"], settings["whisper_device"]
        )
        score = None
        too_short = False
        if text and _is_echo(text):
            log.info("Asistanın kendi sesi duyuldu, yok sayıldı: %s", text)
            return {"text": "", "device": device, "identity": identity.state(), "voice_score": None,
                    "voice_too_short": False, "echo": True}
        if identity.active():
            result = await run_in_threadpool(voiceid.identify, path)
            score, scores = result["score"], voiceid.describe(result["scores"])
            if result["name"]:
                identity.verified_by_voice(result["name"], score, scores)
            elif score is not None:  # enough speech, but nobody we know (or too close to call)
                identity.unknown_voice(score, text, scores)
            else:  # too little speech to tell; the current identity stays
                too_short = True
    except ImportError:
        raise HTTPException(500, "Ses tanıma paketi (faster-whisper) kurulu değil. kurulum.bat'ı tekrar çalıştır.")
    except Exception as e:
        log.exception("Ses tanıma başarısız oldu")
        raise HTTPException(500, f"Ses tanınamadı: {e}")
    finally:
        os.remove(path)
    return {"text": text, "device": device, "identity": identity.state(), "voice_score": score,
            "voice_too_short": too_short}


# Voice profiles and security log

@app.get("/api/voice/profiles")
def voice_profiles():
    _require_admin()
    return [{"id": s["id"], "name": s["name"], "admin": s["is_admin"], "created_at": s["created_at"],
             "has_passcode": bool(s.get("passcode"))} for s in db.list_speakers()]


class PasscodeIn(BaseModel):
    passcode: str = ""  # empty = remove


@app.put("/api/voice/profiles/{speaker_id}/passcode")
def voice_passcode(speaker_id: int, body: PasscodeIn):
    _require_admin()
    target = next((s for s in db.list_speakers() if s["id"] == speaker_id), None)
    if not target:
        raise HTTPException(404, "Profil bulunamadı")
    code = body.passcode.strip()
    if not code:
        db.set_passcode(speaker_id, None)
        db.log_security("Şifre kaldırıldı", target["name"])
        return {"ok": True}
    problem = identity.passcode_problem(code, speaker_id)
    if problem:
        raise HTTPException(400, problem)
    db.set_passcode(speaker_id, identity.hash_passcode(code))
    db.log_security("Şifre belirlendi", target["name"])
    return {"ok": True}


@app.post("/api/voice/enroll")
async def voice_enroll(name: str = Form(...), audio: list[UploadFile] = File(...)):
    _require_admin()
    name = name.strip()
    if not name or len(name) > 30 or any(c.isspace() for c in name):
        raise HTTPException(400, "Ad tek kelime olmalı (en fazla 30 harf).")
    paths = []
    try:
        for upload in audio:
            suffix = Path(upload.filename or "").suffix or ".webm"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await upload.read())
                paths.append(tmp.name)
        first = not identity.active()
        result = await run_in_threadpool(voiceid.enroll, name, paths, first)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except ImportError:
        raise HTTPException(500, "Ses tanıma paketi (sherpa-onnx) kurulu değil. baslat.bat'ı kapatıp yeniden aç.")
    except Exception as e:
        log.exception("Ses profili kaydedilemedi")
        raise HTTPException(500, f"Ses profili kaydedilemedi: {e}")
    finally:
        for path in paths:
            os.remove(path)
    identity.enrolled(name)
    return {**result, "identity": identity.state()}


@app.delete("/api/voice/profiles/{speaker_id}")
def voice_delete(speaker_id: int):
    _require_admin()
    speakers = db.list_speakers()
    target = next((s for s in speakers if s["id"] == speaker_id), None)
    if not target:
        raise HTTPException(404, "Profil bulunamadı")
    if target["is_admin"] and len(speakers) > 1:
        raise HTTPException(400, "Yönetici profili, başka profiller varken silinemez.")
    db.delete_speaker(speaker_id)
    db.log_security("Ses profili silindi", target["name"])
    return {"ok": True, "identity": identity.state()}


@app.get("/api/security-log")
def security_log():
    _require_admin()
    return db.list_security_log()


class TtsIn(BaseModel):
    text: str


@app.post("/api/tts")
async def speak(body: TtsIn):
    voice = config.load()["tts_voice"]
    if voice not in tts.VOICES:
        raise HTTPException(400, "Seçili ses sunucuda seslendirilmiyor")
    text = body.text.strip()[:2000]
    if not text:
        raise HTTPException(400, "Boş metin")
    try:
        audio = await tts.synthesize(text, voice)
    except ImportError:
        raise HTTPException(500, "Ses paketi (edge-tts) kurulu değil. baslat.bat'ı kapatıp yeniden aç.")
    except Exception as e:
        log.warning("Seslendirme başarısız oldu: %s", e)
        raise HTTPException(502, "Microsoft ses servisine ulaşılamadı (internet bağlantını kontrol et)")
    if not audio:
        raise HTTPException(502, "Microsoft ses servisi boş yanıt verdi")
    return Response(audio, media_type="audio/mpeg")
