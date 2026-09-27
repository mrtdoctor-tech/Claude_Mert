"""Online text-to-speech with Microsoft's neural voices (edge-tts).

Only the reply text being read aloud is sent to Microsoft; messages, memories and history stay local.
The "windows" voice needs no server: the browser speaks with the offline Windows voice instead.
"""

VOICES = {
    "tr-TR-EmelNeural": "Emel (kadın)",
    "tr-TR-AhmetNeural": "Ahmet (erkek)",
}


async def synthesize(text: str, voice: str) -> bytes:
    import edge_tts

    audio = bytearray()
    async for chunk in edge_tts.Communicate(text, voice).stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
    return bytes(audio)
