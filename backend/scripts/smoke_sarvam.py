"""Live smoke test for Sarvam AI: Bulbul v3 TTS -> Saaras v3 STT round trip.

Usage: python scripts/smoke_sarvam.py   (needs SARVAM_API_KEY in backend/.env)

For each demo sentence: synthesise it, then transcribe the audio back with mode="codemix" and with
mode="transcribe" + hi-IN, and report latency and how close the transcript is to the original.
Audio files are written to scripts/_smoke_audio/ (gitignored) so you can listen to them.
"""
import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rapidfuzz import fuzz  # noqa: E402

from app.config import get_settings  # noqa: E402

SENTENCES = [
    "Sunita ji ne 650 ka udhaar liya, Friday tak denge",
    "Agarwal ka payment 7 tareekh ko kar do",
    "सुनीता जी ने 650 का उधार लिया, शुक्रवार तक देंगे",
    "Paytm par 650 rupaye prapt hue",
]
KEYTERMS = ["Sunita", "Agarwal", "udhaar", "tareekh", "Paytm", "Sharma"]
OUT = Path(__file__).parent / "_smoke_audio"


def main() -> int:
    s = get_settings()
    if not s.sarvam_api_key:
        print("SARVAM_API_KEY is not set in backend/.env")
        return 1
    import sarvamai
    from sarvamai import SarvamAI

    print(f"sarvamai {getattr(sarvamai, '__version__', '?')}, speaker {s.sarvam_tts_speaker}")
    client = SarvamAI(api_subscription_key=s.sarvam_api_key)
    OUT.mkdir(exist_ok=True)
    for i, text in enumerate(SENTENCES):
        t0 = time.perf_counter()
        tts = client.text_to_speech.convert(text=text, language_code="hi-IN", speaker=s.sarvam_tts_speaker,
                                            model="bulbul:v3", output_audio_codec="mp3")
        t_tts = time.perf_counter() - t0
        audio = base64.b64decode(tts.audios[0])
        path = OUT / f"s{i}.mp3"
        path.write_bytes(audio)
        print(f"\n[{i}] {text}\n    TTS {t_tts:.2f}s, {len(audio):,} bytes, {len(tts.audios)} chunk(s) -> {path.name}")
        # saaras:v3 is the spec'd model; keyterms are v4-only, so v4 is shown for comparison.
        for model, mode, extra in (("saaras:v3", "codemix", {}), ("saaras:v3", "transcribe", {}),
                                   ("saaras:v4", "codemix", {"keyterms": KEYTERMS})):
            t0 = time.perf_counter()
            stt = client.speech_to_text.transcribe(file=(path.name, audio, "audio/mpeg"), model=model,
                                                   mode=mode, language_code="hi-IN", **extra)
            dt = time.perf_counter() - t0
            score = fuzz.token_set_ratio(text.lower(), stt.transcript.lower())
            label = f"{model} {mode}" + ("+keyterms" if extra else "")
            print(f"    STT {label:28s} {dt:.2f}s  match {score:5.1f}  -> {stt.transcript!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
