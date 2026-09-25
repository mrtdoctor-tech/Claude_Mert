"""Long-term memory: builds the system prompt and learns new facts after each reply."""

import logging
from datetime import datetime

from . import db, llm

log = logging.getLogger("asistan.memory")

MAX_MEMORIES_IN_PROMPT = 200
DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

EXTRACT_PROMPT = """You maintain the long-term memory of a personal assistant about its user.
You get the facts already known and the latest exchange between the user and the assistant.
Extract only NEW, lasting facts about the user that will be useful in future conversations:
name, family, friends, job, health, preferences, habits, goals, important dates, ongoing projects,
and anything the user explicitly asks to be remembered.
Skip small talk, one-off questions, temporary states and facts that are already known.
Write each fact as one short standalone sentence in the language the user writes in.
Answer with JSON only: {"memories": ["..."]}. If there is nothing new: {"memories": []}"""


def system_prompt(settings: dict) -> str:
    now = datetime.now()
    today = f"{now:%d.%m.%Y}, {DAYS_TR[now.weekday()]}, saat {now:%H:%M}"
    memories = db.list_memories()[-MAX_MEMORIES_IN_PROMPT:]
    if memories:
        known = "\n".join(f"- {m['content']}" for m in memories)
    else:
        known = "- Henüz kayıtlı bir bilgi yok."
    return f"""Sen {settings['assistant_name']}, kullanıcının kişisel yapay zekâ asistanısın.
Tamamen kullanıcının kendi bilgisayarında çalışıyorsun; konuşmalar hiçbir yere gönderilmiyor.
Samimi, net ve yardımsever ol. Kullanıcı hangi dilde yazarsa o dilde yanıt ver.
Yanıtlarını gereksiz uzatma; sesli okunabilecekleri için sade tut.

Şu an: {today}

Önceki sohbetlerden kullanıcı hakkında hatırladıkların:
{known}

Bu bilgileri doğal şekilde kullan; kullanıcı istemedikçe listeyi olduğu gibi tekrarlama."""


async def extract(model: str, user_text: str, reply: str):
    known = [m["content"] for m in db.list_memories()]
    known_text = "\n".join(f"- {k}" for k in known) or "(none)"
    exchange = f"Known facts:\n{known_text}\n\nUser: {user_text}\n\nAssistant: {reply}"
    try:
        data = await llm.chat_json(
            model,
            [{"role": "system", "content": EXTRACT_PROMPT}, {"role": "user", "content": exchange}],
        )
    except Exception:
        log.exception("Hafıza çıkarımı başarısız oldu")
        return

    items = data.get("memories", []) if isinstance(data, dict) else []
    seen = {k.casefold() for k in known}
    for item in items:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text and len(text) <= 300 and text.casefold() not in seen:
            db.add_memory(text)
            seen.add(text.casefold())
