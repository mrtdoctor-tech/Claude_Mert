"""Long-term memory: builds the system prompt and learns new facts while the user is idle."""

import asyncio
import logging
from datetime import datetime

from . import db, llm

log = logging.getLogger("asistan.memory")

MAX_MEMORIES_IN_PROMPT = 200
# Learning runs only after the user has been quiet this long, so it never competes
# with a reply (or with speech/voice recognition) for the CPU.
IDLE_SECONDS = 30
BATCH_SIZE = 20
_CURSOR_KEY = "memory_cursor"  # id of the last message already scanned for facts
DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

EXTRACT_PROMPT = """You maintain the long-term memory of a personal assistant about its user.
You get the facts already known and the latest messages between the user and the assistant.
Extract only NEW, lasting facts about the user that will be useful in future conversations:
name, family, friends, job, health, preferences, habits, goals, important dates, ongoing projects,
and anything the user explicitly asks to be remembered.
Skip small talk, one-off questions, temporary states and facts that are already known.
Write each fact as one short standalone sentence in the language the user writes in.
Answer with JSON only: {"memories": ["..."]}. If there is nothing new: {"memories": []}"""


def system_prompt(settings: dict) -> str:
    # Date only (no clock time): an unchanged prompt lets Ollama reuse its cache, which is much faster.
    now = datetime.now()
    today = f"{now:%d.%m.%Y}, {DAYS_TR[now.weekday()]}"
    memories = db.list_memories()[-MAX_MEMORIES_IN_PROMPT:]
    if memories:
        known = "\n".join(f"- {m['content']}" for m in memories)
    else:
        known = "- Henüz kayıtlı bir bilgi yok."
    return f"""Sen {settings['assistant_name']}, kullanıcının kişisel yapay zekâ asistanısın.
Tamamen kullanıcının kendi bilgisayarında çalışıyorsun; konuşmalar hiçbir yere gönderilmiyor.
Samimi, net ve yardımsever ol. Kullanıcı hangi dilde yazarsa o dilde yanıt ver.
Yanıtlarını gereksiz uzatma; sesli okunabilecekleri için sade tut.

Bugün: {today}

Önceki sohbetlerden kullanıcı hakkında hatırladıkların:
{known}

Bu bilgileri doğal şekilde kullan; kullanıcı istemedikçe listeyi olduğu gibi tekrarlama."""


_pending: asyncio.Task | None = None


def init_cursor():
    """Called at startup. Databases from the first version already learned from every reply."""
    if db.get_meta(_CURSOR_KEY) is None:
        db.set_meta(_CURSOR_KEY, str(db.last_message_id()))


def schedule(model: str):
    """(Re)start the idle countdown after which new messages are scanned for facts."""
    global _pending
    cancel()
    _pending = asyncio.create_task(_run_when_idle(model))


def cancel():
    """Stop a pending or running scan; the messages stay queued for the next one."""
    if _pending and not _pending.done():
        _pending.cancel()


async def _run_when_idle(model: str):
    await asyncio.sleep(IDLE_SECONDS)
    try:
        while await _extract_batch(model):
            pass
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Hafıza çıkarımı başarısız oldu")


async def _extract_batch(model: str) -> bool:
    """Scan the next unprocessed messages. Returns True if more are waiting."""
    messages = db.messages_after(int(db.get_meta(_CURSOR_KEY) or 0), BATCH_SIZE)
    if not messages:
        return False

    if any(m["role"] == "user" for m in messages):
        known = [m["content"] for m in db.list_memories()]
        known_text = "\n".join(f"- {k}" for k in known) or "(none)"
        dialogue = "\n\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in messages
        )
        data = await llm.chat_json(
            model,
            [
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": f"Known facts:\n{known_text}\n\nMessages:\n{dialogue}"},
            ],
        )
        _save(data, known)

    db.set_meta(_CURSOR_KEY, str(messages[-1]["id"]))
    return len(messages) == BATCH_SIZE


def _save(data, known: list[str]):
    items = data.get("memories", []) if isinstance(data, dict) else []
    seen = {k.casefold() for k in known}
    for item in items:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text and len(text) <= 300 and text.casefold() not in seen:
            db.add_memory(text)
            seen.add(text.casefold())
