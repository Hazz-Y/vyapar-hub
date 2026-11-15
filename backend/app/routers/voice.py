import json
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.agent.runner import run_agent
from app.deps import MerchantId, SessionDep
from app.routers.agent import make_context
from app.services import speech

router = APIRouter(prefix="/voice", tags=["voice"])


async def _read_audio(audio: UploadFile) -> bytes:
    data = await audio.read()
    if not data:
        raise HTTPException(422, "empty audio")
    if len(data) > speech.MAX_AUDIO_BYTES:
        raise HTTPException(413, "audio too long: keep recordings under 25 seconds")
    return data


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    data = await _read_audio(audio)
    try:
        return speech.transcribe(data, audio.content_type, audio.filename)
    except speech.SpeechUnavailable as e:
        raise HTTPException(503, {"error": "stt_unavailable", "fallback": "typed_input", "reason": str(e)})


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    language_code: str = "hi-IN"


@router.post("/speak")
def speak(body: SpeakRequest) -> dict:
    from app.services.hardware import display_from_speech
    display_from_speech(body.text)
    return speech.speak(body.text, body.language_code)


@router.post("/turn")
async def turn(session: SessionDep, audio: UploadFile = File(...), history: str = Form("[]"),
               merchant_id: MerchantId = 1) -> dict:
    """Transcribe -> agent -> speak in one round trip."""
    t0 = time.perf_counter()
    data = await _read_audio(audio)
    try:
        stt = speech.transcribe(data, audio.content_type, audio.filename)
    except speech.SpeechUnavailable as e:
        raise HTTPException(503, {"error": "stt_unavailable", "fallback": "typed_input", "reason": str(e)})
    if not stt["transcript"]:
        return {"transcript": "", "reply_text": "Maaf kijiye, awaaz saaf nahi aayi. Phir se boliye.",
                "pending_actions": [], "tool_trace": [], "audio": None, "timings": {"stt_ms": stt["ms"]}}
    try:
        hist = json.loads(history)
        hist = hist if isinstance(hist, list) else []
    except json.JSONDecodeError:
        hist = []
    t1 = time.perf_counter()
    result = run_agent(make_context(session, merchant_id), stt["transcript"], hist)
    t2 = time.perf_counter()
    audio_out = speech.speak(result["reply_text"])
    return {"transcript": stt["transcript"], "raw_transcript": stt["raw_transcript"], **result,
            "audio": audio_out,
            "timings": {"stt_ms": stt["ms"], "agent_ms": int((t2 - t1) * 1000), "tts_ms": audio_out["ms"],
                        "total_ms": int((time.perf_counter() - t0) * 1000)}}
