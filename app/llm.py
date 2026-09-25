"""Minimal client for the local Ollama server."""

import json
import os

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
TIMEOUT = httpx.Timeout(600.0, connect=5.0)


class OllamaError(Exception):
    pass


def _error_for(status: int, body: str, model: str) -> OllamaError:
    if status == 404:
        return OllamaError(
            f"'{model}' modeli yüklü değil. Komut isteminde şunu çalıştır: ollama pull {model}"
        )
    return OllamaError(f"Ollama hatası ({status}): {body[:300]}")


_CONNECT_ERROR = "Ollama'ya bağlanılamadı. Ollama uygulamasının açık olduğundan emin ol."


async def list_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
    except httpx.ConnectError as e:
        raise OllamaError(_CONNECT_ERROR) from e
    return sorted(m["name"] for m in resp.json().get("models", []))


async def chat_stream(model: str, messages: list[dict]):
    """Yield the reply text piece by piece as Ollama generates it."""
    payload = {"model": model, "messages": messages, "stream": True}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", "replace")
                    raise _error_for(resp.status_code, body, model)
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise OllamaError(chunk["error"])
                    text = chunk.get("message", {}).get("content", "")
                    if text:
                        yield text
                    if chunk.get("done"):
                        break
    except httpx.ConnectError as e:
        raise OllamaError(_CONNECT_ERROR) from e


async def chat_json(model: str, messages: list[dict]) -> dict:
    """Ask for a JSON-only answer (used for memory extraction)."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
    except httpx.ConnectError as e:
        raise OllamaError(_CONNECT_ERROR) from e
    if resp.status_code != 200:
        raise _error_for(resp.status_code, resp.text, model)
    return json.loads(resp.json()["message"]["content"])
