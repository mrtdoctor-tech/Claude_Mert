"""Long-term memory: builds the system prompt and learns new facts while the user is idle."""

import asyncio
import logging
import re
from datetime import datetime

from . import db, llm
from .quick import DAYS_TR

log = logging.getLogger("asistan.memory")

MAX_MEMORIES_IN_PROMPT = 200
# Learning runs only after the user has been quiet this long. It uses the same model as the chat,
# and every other request wipes the model's cached reading of the conversation (Ollama keeps one),
# so on a slow computer it must not run between the messages of an ongoing conversation.
IDLE_SECONDS = 300
BATCH_SIZE = 20
_CURSOR_KEY = "memory_cursor"  # id of the last message already scanned for facts

EXTRACT_PROMPT_TR = """Kişisel bir asistanın, kullanıcısı hakkındaki uzun süreli hafızasını tutuyorsun.
Sana zaten bilinen bilgiler ve kullanıcının son mesajları verilecek.
Yalnızca kullanıcının bu mesajlarda AÇIKÇA söylediği, YENİ ve kalıcı bilgileri çıkar: adı, ailesi, arkadaşları,
işi, sağlığı, yaşadığı yer, tercihleri, alışkanlıkları, hedefleri, önemli tarihler, süren işleri ve
"bunu hatırla" dediği her şey.
Selamlaşma, sorular, geçici durumlar ve zaten bilinen bilgileri (başka kelimelerle de olsa) ATLA.
Tahmin etme, uydurma. Her bilgiyi kısa, tek başına anlaşılır bir TÜRKÇE cümle olarak yaz ve kullanıcıdan
"Kullanıcı" diye bahset (örnek: "Kullanıcının adı Mert.").
Yalnızca JSON döndür: {"memories": ["..."]}. Yeni bilgi yoksa: {"memories": []}"""

EXTRACT_PROMPT_EN = """You maintain the long-term memory of a personal assistant about its user.
You get the facts already known and the user's latest messages.
Extract only NEW, lasting facts the user EXPLICITLY states in these messages: name, family, friends, job, health,
where they live, preferences, habits, goals, important dates, ongoing projects, and anything they ask to be remembered.
SKIP greetings, questions, temporary states and facts already known (even if worded differently).
Do not guess or invent. Write each fact as one short standalone sentence and refer to the user as "The user".
Answer with JSON only: {"memories": ["..."]}. If there is nothing new: {"memories": []}"""


def clock_note() -> str:
    """Current date and time, added to the newest user message only.

    Keeping it out of the system prompt leaves the prompt unchanged between messages,
    so Ollama can reuse its cache (much faster on a slow computer).
    """
    now = datetime.now()
    return f"\n\n(Şu an: {now:%d.%m.%Y}, {DAYS_TR[now.weekday()]}, saat {now:%H:%M})"


_prompts: dict[int, tuple[str, str]] = {}  # conversation id -> (assistant name, system prompt)


def system_prompt_for(conversation_id: int, settings: dict) -> str:
    """The system prompt is fixed for the whole conversation.

    If it changed whenever a new fact was learned, the model would have to re-read the entire
    conversation from scratch (minutes on a slow computer). New facts apply from the next conversation;
    the current one already contains them anyway.
    """
    cached = _prompts.get(conversation_id)
    if cached is None or cached[0] != settings["assistant_name"]:
        cached = (settings["assistant_name"], system_prompt(settings))
        _prompts[conversation_id] = cached
    return cached[1]


def system_prompt(settings: dict) -> str:
    memories = db.list_memories()[-MAX_MEMORIES_IN_PROMPT:]
    if memories:
        known = "\n".join(f"- {m['content']}" for m in memories)
    else:
        known = "- Henüz kayıtlı bir bilgi yok."
    return f"""Sen {settings['assistant_name']}, kullanıcının kişisel yapay zekâ asistanısın.
Tamamen kullanıcının kendi bilgisayarında çalışıyorsun; konuşmalar hiçbir yere gönderilmiyor.
Samimi, net ve yardımsever ol. Kullanıcı hangi dilde yazarsa o dilde yanıt ver.
Yanıtlarını gereksiz uzatma; sesli okunabilecekleri için sade tut.

Kullanıcının son mesajının sonundaki "(Şu an: ...)" notunu sistem ekler: tarih ve saati oradan al,
sorulmadıkça bu nottan bahsetme.

Önceki sohbetlerden kullanıcı hakkında hatırladıkların:
{known}

Bu bilgileri doğal şekilde kullan; kullanıcı istemedikçe listeyi olduğu gibi tekrarlama.
Hafızaya kaydı sen yapmazsın: yeni bilgiler sohbetten sonra kendiliğinden kaydedilir ve Hafıza bölümünde görünür.
"Kaydettin mi?" diye sorulursa bunu dürüstçe söyle; kaydettiğini iddia etme."""


_pending: asyncio.Task | None = None
_learning = asyncio.Lock()  # one scan at a time, otherwise parallel scans save the same facts twice


def _model_for(settings: dict) -> str:
    return settings.get("memory_model") or settings["model"]


def init_cursor():
    """Called at startup. Databases from the first version already learned from every reply."""
    if db.get_meta(_CURSOR_KEY) is None:
        db.set_meta(_CURSOR_KEY, str(db.last_message_id()))


def schedule(settings: dict):
    """(Re)start the idle countdown after which new messages are scanned for facts."""
    global _pending
    cancel()
    _pending = asyncio.create_task(_run_when_idle(settings))


def cancel():
    """Stop a pending or running scan; the messages stay queued for the next one."""
    if _pending and not _pending.done():
        _pending.cancel()


async def learn_now(settings: dict) -> int:
    """Scan every unprocessed message now. Returns how many new facts were saved."""
    cancel()
    return await _learn_all(settings)


async def _run_when_idle(settings: dict):
    await asyncio.sleep(IDLE_SECONDS)
    try:
        await _learn_all(settings)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Hafıza çıkarımı başarısız oldu")


async def _learn_all(settings: dict) -> int:
    async with _learning:
        added, more = 0, True
        while more:
            count, more = await _extract_batch(settings)
            added += count
        return added


async def _extract_batch(settings: dict) -> tuple[int, bool]:
    """Scan the next unprocessed messages. Returns (facts saved, more messages waiting)."""
    messages = db.messages_after(int(db.get_meta(_CURSOR_KEY) or 0), BATCH_SIZE)
    if not messages:
        return 0, False
    added = 0

    # Only the user's own words: the assistant's replies made small models "learn" things like
    # "I saved your name to memory".
    said = [m["content"] for m in messages if m["role"] == "user"]
    if said:
        known = [m["content"] for m in db.list_memories()]
        turkish = settings.get("language", "tr") in ("tr", "")
        known_text = "\n".join(f"- {k}" for k in known) or ("(yok)" if turkish else "(none)")
        said_text = "\n".join(f"- {t}" for t in said)
        if turkish:
            prompt, request = EXTRACT_PROMPT_TR, f"Bilinen bilgiler:\n{known_text}\n\nKullanıcının mesajları:\n{said_text}"
        else:
            prompt, request = EXTRACT_PROMPT_EN, f"Known facts:\n{known_text}\n\nThe user's messages:\n{said_text}"
        model = _model_for(settings)
        # A separate memory model is only needed now and then: let Ollama free its RAM soon after.
        keep_alive = llm.KEEP_ALIVE if model == settings["model"] else "2m"
        data = await llm.chat_json(
            model,
            [{"role": "system", "content": prompt}, {"role": "user", "content": request}],
            keep_alive=keep_alive,
        )
        added = _save(data, known)

    db.set_meta(_CURSOR_KEY, str(messages[-1]["id"]))
    return added, len(messages) == BATCH_SIZE


def _facts(data) -> list[str]:
    """Small models do not always follow the JSON shape exactly; accept the common variations."""
    if isinstance(data, dict):
        items = data.get("memories")
        if items is None:  # another key name, e.g. {"facts": [...]}
            items = next((v for v in data.values() if isinstance(v, (list, str))), [])
    else:
        items = data
    if isinstance(items, str):
        items = [items]
    if not isinstance(items, list):
        return []
    facts = []
    for item in items:
        if isinstance(item, dict):  # e.g. {"fact": "..."}
            item = next((v for v in item.values() if isinstance(v, str)), None)
        if isinstance(item, str):
            facts.append(item)
    return facts


def _key(text: str) -> str:
    """Comparison form: "Kullanıcının adı Mert." and "kullanıcının adı mert" are the same fact."""
    return re.sub(r"[\s.!?,;:]+", " ", text).strip().casefold()


def _save(data, known: list[str]) -> int:
    seen = {_key(k) for k in known}
    added = 0
    for item in _facts(data):
        text = item.strip()
        if text and len(text) <= 300 and _key(text) not in seen:
            db.add_memory(text)
            seen.add(_key(text))
            added += 1
    return added
