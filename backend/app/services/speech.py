"""Sarvam AI speech: Saaras v3 speech-to-text and Bulbul v3 text-to-speech, with fallbacks.

Fallbacks (no SARVAM_API_KEY, or the API fails):
* STT raises SpeechUnavailable -> the UI falls back to typed input;
* TTS returns audio_b64=None, provider="browser" -> the UI speaks with window.speechSynthesis.
"""
from __future__ import annotations

import base64
import re
import time
from functools import lru_cache

from app.config import get_settings
from app.services.numbers import words_to_digits

STT_MODEL = "saaras:v3"
STT_MODE = "codemix"  # keeps English words (payment, Friday) in Roman; compared with "transcribe" in smoke test
TTS_MODEL = "bulbul:v3"
TTS_MAX_CHARS = 2500  # Bulbul limit per request
MAX_AUDIO_BYTES = 2_000_000  # ~25 s of browser WebM/Opus is well under this

CODECS = {"audio/webm": "webm", "video/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav",
          "audio/x-wav": "wav", "audio/wave": "wav", "audio/mpeg": "mp3", "audio/mp3": "mp3",
          "audio/mp4": "mp4", "audio/x-m4a": "x-m4a", "audio/aac": "aac", "audio/flac": "flac"}

MONTHS = {"Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April", "Jun": "June", "Jul": "July",
          "Aug": "August", "Sep": "September", "Oct": "October", "Nov": "November", "Dec": "December"}


class SpeechUnavailable(Exception):
    """Sarvam is not configured or failed; the caller should use the fallback."""


@lru_cache
def _client():
    from sarvamai import SarvamAI

    return SarvamAI(api_subscription_key=get_settings().sarvam_api_key)


def get_client():
    if not get_settings().sarvam_api_key:
        raise SpeechUnavailable("SARVAM_API_KEY not set")
    return _client()


def codec_for(content_type: str | None, filename: str | None = None) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in CODECS:
        return CODECS[ct]
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    return {"webm": "webm", "ogg": "ogg", "wav": "wav", "mp3": "mp3", "m4a": "x-m4a", "mp4": "mp4"}.get(ext, "webm")


def transcribe(audio: bytes, content_type: str | None = None, filename: str | None = None,
               language_code: str = "hi-IN") -> dict:
    if not audio:
        raise ValueError("empty audio")
    if len(audio) > MAX_AUDIO_BYTES:
        raise ValueError("audio too long: keep recordings under 25 seconds")
    client = get_client()
    codec = codec_for(content_type, filename)
    t0 = time.perf_counter()
    try:
        resp = client.speech_to_text.transcribe(
            file=(filename or f"audio.{codec}", audio, (content_type or "audio/webm").split(";")[0]),
            model=STT_MODEL, mode=STT_MODE, language_code=language_code, input_audio_codec=codec)
    except Exception as e:
        raise SpeechUnavailable(f"{type(e).__name__}: {str(e)[:200]}") from e
    raw = (resp.transcript or "").strip()
    return {"transcript": words_to_digits(raw), "raw_transcript": raw, "language_code": resp.language_code,
            "provider": "sarvam", "model": STT_MODEL, "mode": STT_MODE,
            "ms": int((time.perf_counter() - t0) * 1000)}


def spoken_form(text: str) -> str:
    """Make app text sound natural: '₹22,000' -> '22,000 rupaye', '20 Nov (Friday)' -> '20 November, Friday'."""
    amount = r"(\d(?:[\d,]*\d)?)"  # must end on a digit: "₹650," keeps its comma outside
    t = re.sub(r"-₹\s?" + amount, r"minus \1 rupaye", text)
    t = re.sub(r"₹\s?" + amount, r"\1 rupaye", t)
    t = re.sub(r"\b(\d{1,2}) (" + "|".join(MONTHS) + r")\b", lambda m: f"{m.group(1)} {MONTHS[m.group(2)]}", t)
    t = re.sub(r"\s*\((\w+day)\)", r", \1", t)
    t = re.sub(r"UPI \S+@\S+", "UPI par", t)  # don't spell out VPAs
    return re.sub(r"\s+", " ", t).strip()


def chunk_text(text: str, limit: int = TTS_MAX_CHARS) -> list[str]:
    """Split on sentence boundaries so each chunk fits the TTS limit."""
    if len(text) <= limit:
        return [text]
    sentences = re.split(r"(?<=[.?!।])\s+", text)
    chunks, cur = [], ""
    for s in sentences:
        while len(s) > limit:  # one very long sentence: hard split on a space
            cut = s.rfind(" ", 0, limit) or limit
            chunks.append((cur + " " + s[:cut]).strip() if cur else s[:cut])
            cur, s = "", s[cut:].strip()
        if len(cur) + len(s) + 1 > limit:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def speak(text: str, language_code: str = "hi-IN", speaker: str | None = None) -> dict:
    """Returns base64 MP3, or a browser-fallback marker if Sarvam is unavailable."""
    spoken = spoken_form(text)
    t0 = time.perf_counter()
    try:
        client = get_client()
        audio = b""
        chunks = chunk_text(spoken)
        for chunk in chunks:
            resp = client.text_to_speech.convert(
                text=chunk, language_code=language_code, speaker=speaker or get_settings().sarvam_tts_speaker,
                model=TTS_MODEL, output_audio_codec="mp3")
            audio += b"".join(base64.b64decode(a) for a in resp.audios)  # MP3 frames concatenate cleanly
    except Exception as e:
        return {"audio_b64": None, "mime": None, "provider": "browser", "text": text, "spoken_text": spoken,
                "reason": f"{type(e).__name__}: {str(e)[:200]}", "ms": int((time.perf_counter() - t0) * 1000)}
    return {"audio_b64": base64.b64encode(audio).decode(), "mime": "audio/mpeg", "provider": "sarvam",
            "text": text, "spoken_text": spoken, "chunks": len(chunks), "model": TTS_MODEL,
            "ms": int((time.perf_counter() - t0) * 1000)}
