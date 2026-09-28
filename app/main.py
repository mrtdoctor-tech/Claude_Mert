"""Local web server: serves the UI and the chat/memory/voice API."""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, llm, memory, presence, quick, stt, tts

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
    memory.init_cursor()
    memory.schedule(config.load())
    other = presence.other_computer()
    if other:
        log.warning("DİKKAT: Asistan şu anda %s bilgisayarında da açık görünüyor.", other)
    _presence_task = asyncio.create_task(presence.keep_marking())
    _background.add(_presence_task)


_background: set = set()  # keeps background tasks referenced


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


@app.get("/api/version")
def version():
    return {"version": config.VERSION, "other_computer": presence.other_computer()}


# Settings

class SettingsIn(BaseModel):
    assistant_name: str | None = None
    model: str | None = None
    whisper_model: str | None = None
    language: str | None = None
    tts_voice: str | None = None
    auto_listen: bool | None = None
    memory_model: str | None = None


@app.get("/api/settings")
def get_settings():
    return config.load()


@app.put("/api/settings")
def put_settings(body: SettingsIn):
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
    return db.list_conversations()


@app.get("/api/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int):
    if not db.get_conversation(conversation_id):
        raise HTTPException(404, "Sohbet bulunamadı")
    return db.list_messages(conversation_id)


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: int):
    db.delete_conversation(conversation_id)
    return {"ok": True}


class ChatIn(BaseModel):
    message: str
    conversation_id: int | None = None


@app.post("/api/chat")
async def chat(body: ChatIn):
    text = body.message.strip()
    if not text:
        raise HTTPException(400, "Mesaj boş olamaz")

    conversation_id = body.conversation_id
    if conversation_id is None or not db.get_conversation(conversation_id):
        title = text if len(text) <= 50 else text[:47].rstrip() + "..."
        conversation_id = db.create_conversation(title)

    memory.cancel()  # free the CPU for the reply
    history = db.list_messages(conversation_id)
    start = max(0, len(history) - HISTORY_LIMIT)
    history = history[start - start % HISTORY_STEP:]
    db.add_message(conversation_id, "user", text)

    settings = config.load()
    messages = [{"role": "system", "content": memory.system_prompt_for(conversation_id, settings)}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": text + memory.clock_note()})  # the note is not saved
    instant = quick.answer(text)  # "saat kaç?" etc. come from the clock, not the model

    async def from_clock():
        yield instant

    async def stream():
        yield _line({"type": "meta", "conversation_id": conversation_id, "instant": bool(instant)})
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
        reply = "".join(parts).strip()
        if reply:
            db.add_message(conversation_id, "assistant", reply)
        yield _line({"type": "done"})

    return StreamingResponse(stream(), media_type="application/x-ndjson")


# Memories

class MemoryIn(BaseModel):
    content: str


@app.get("/api/memories")
def memories():
    return db.list_memories()


@app.post("/api/memories")
def add_memory(body: MemoryIn):
    content = body.content.strip()
    if not content:
        raise HTTPException(400, "Boş bilgi eklenemez")
    return {"id": db.add_memory(content)}


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
    db.delete_memory(memory_id)
    return {"ok": True}


# Voice

@app.post("/api/transcribe/warmup")
async def transcribe_warmup():
    """Load the speech model while the user is still talking."""
    settings = config.load()
    memory.schedule(settings)  # restart the idle countdown (it must never be dropped)
    try:
        await run_in_threadpool(stt.load, settings["whisper_model"])
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
        text = await run_in_threadpool(
            stt.transcribe, path, settings["whisper_model"], settings["language"]
        )
    except ImportError:
        raise HTTPException(500, "Ses tanıma paketi (faster-whisper) kurulu değil. kurulum.bat'ı tekrar çalıştır.")
    except Exception as e:
        log.exception("Ses tanıma başarısız oldu")
        raise HTTPException(500, f"Ses tanınamadı: {e}")
    finally:
        os.remove(path)
    return {"text": text}


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
