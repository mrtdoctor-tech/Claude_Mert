"""Local web server: serves the UI and the chat/memory/voice API."""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, llm, memory, stt

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("asistan")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
HISTORY_LIMIT = 30  # previous messages of the current conversation sent to the model

app = FastAPI(title="Yerel Asistan")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
db.init()

# Keep references so background memory tasks are not garbage-collected mid-run.
_background: set[asyncio.Task] = set()


def _spawn(coro):
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


def _line(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# Settings

class SettingsIn(BaseModel):
    assistant_name: str | None = None
    model: str | None = None
    whisper_model: str | None = None
    language: str | None = None


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

    history = db.list_messages(conversation_id)[-HISTORY_LIMIT:]
    db.add_message(conversation_id, "user", text)

    settings = config.load()
    messages = [{"role": "system", "content": memory.system_prompt(settings)}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": text})

    async def stream():
        yield _line({"type": "meta", "conversation_id": conversation_id})
        parts = []
        try:
            async for piece in llm.chat_stream(settings["model"], messages):
                parts.append(piece)
                yield _line({"type": "token", "text": piece})
        except llm.OllamaError as e:
            yield _line({"type": "error", "message": str(e)})
            return
        reply = "".join(parts).strip()
        if reply:
            db.add_message(conversation_id, "assistant", reply)
            _spawn(memory.extract(settings["model"], text, reply))
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


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int):
    db.delete_memory(memory_id)
    return {"ok": True}


# Voice

@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    settings = config.load()
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
