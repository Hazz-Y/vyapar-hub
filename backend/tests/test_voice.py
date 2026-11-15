import base64
from types import SimpleNamespace

import pytest

from app.services import speech
from app.services.numbers import words_to_digits


class FakeSarvam:
    def __init__(self, transcript="सुनीता जी ने छः सौ पचास का उधार लिया, शुक्रवार तक देंगे।"):
        self.transcript = transcript
        self.stt_calls, self.tts_calls = [], []
        self.speech_to_text = SimpleNamespace(transcribe=self._transcribe)
        self.text_to_speech = SimpleNamespace(convert=self._convert)

    def _transcribe(self, **kw):
        self.stt_calls.append(kw)
        return SimpleNamespace(transcript=self.transcript, language_code="hi-IN")

    def _convert(self, **kw):
        self.tts_calls.append(kw)
        return SimpleNamespace(audios=[base64.b64encode(b"ID3fake-mp3-" + kw["text"][:5].encode()).decode()])


@pytest.fixture
def fake_sarvam(monkeypatch):
    fake = FakeSarvam()
    monkeypatch.setattr(speech, "get_client", lambda: fake)
    return fake


@pytest.mark.parametrize("text,expected", [
    ("सुनीता जी ने छः सौ पचास का उधार लिया", "सुनीता जी ने 650 का उधार लिया"),
    ("शर्मा जी को पाँच हज़ार भेजो", "शर्मा जी को 5000 भेजो"),
    ("Sharma ji ko paanch hazaar bhejo", "Sharma ji ko 5000 bhejo"),
    ("बाईस हज़ार", "22000"),
    ("ढाई हज़ार", "2500"),
    ("ek lakh pachas hazaar", "150000"),
    ("5 हज़ार भेजो", "5000 भेजो"),
    ("सात तारीख को", "7 तारीख को"),
    ("अग्रवाल का पेमेंट 7 तारीख को कर दो", "अग्रवाल का पेमेंट 7 तारीख को कर दो"),  # "दो" = give
    ("kar do", "kar do"),
    ("Sunita ji ne 650 ka udhaar liya", "Sunita ji ne 650 ka udhaar liya"),
])
def test_words_to_digits(text, expected):
    assert words_to_digits(text) == expected


def test_spoken_form():
    assert speech.spoken_form("Agarwal ka ₹22,000 payment 20 Nov (Friday) se 7 Dec (Monday) ko") == \
        "Agarwal ka 22,000 rupaye payment 20 November, Friday se 7 December, Monday ko"
    assert speech.spoken_form("balance -₹7,637 tak") == "balance minus 7,637 rupaye tak"
    assert speech.spoken_form("₹5,000 Sharma Milk Dairy ko bhejna hai, UPI sharmadairy@ybl. Sahi hai?") == \
        "5,000 rupaye Sharma Milk Dairy ko bhejna hai, UPI par Sahi hai?"


def test_chunk_text_respects_limit():
    text = " ".join(f"Yeh vakya number {i} hai." for i in range(400))
    chunks = speech.chunk_text(text, 2500)
    assert len(chunks) > 1 and all(len(c) <= 2500 for c in chunks)
    assert " ".join(chunks) == text
    assert speech.chunk_text("chhota", 2500) == ["chhota"]
    long_word_run = "a " * 3000
    assert all(len(c) <= 2500 for c in speech.chunk_text(long_word_run.strip(), 2500))


def test_codec_for():
    assert speech.codec_for("audio/webm;codecs=opus") == "webm"
    assert speech.codec_for("audio/mp4") == "mp4"
    assert speech.codec_for(None, "clip.wav") == "wav"
    assert speech.codec_for("application/octet-stream", "x.bin") == "webm"


def test_transcribe_without_key_is_503_with_fallback(client):
    r = client.post("/voice/transcribe", files={"audio": ("a.webm", b"\x1aE\xdf\xa3fake", "audio/webm")})
    assert r.status_code == 503 and r.json()["detail"]["fallback"] == "typed_input"


def test_speak_without_key_uses_browser(client):
    r = client.post("/voice/speak", json={"text": "Paytm par ₹650 prapt hue"}).json()
    assert r["provider"] == "browser" and r["audio_b64"] is None
    assert r["spoken_text"] == "Paytm par 650 rupaye prapt hue"


def test_transcribe_with_sarvam(client, fake_sarvam):
    r = client.post("/voice/transcribe", files={"audio": ("rec.webm", b"\x1aE\xdf\xa3fake", "audio/webm;codecs=opus")})
    assert r.status_code == 200
    body = r.json()
    assert body["transcript"] == "सुनीता जी ने 650 का उधार लिया, शुक्रवार तक देंगे।"
    assert body["raw_transcript"].startswith("सुनीता जी ने छः सौ पचास")
    call = fake_sarvam.stt_calls[0]
    assert call["model"] == "saaras:v3" and call["mode"] == "codemix" and call["input_audio_codec"] == "webm"


def test_speak_with_sarvam_chunks(fake_sarvam):
    long = " ".join(f"Vakya {i} hai." for i in range(600))
    r = speech.speak(long)
    assert r["provider"] == "sarvam" and r["chunks"] == len(fake_sarvam.tts_calls) > 1
    assert all(len(c["text"]) <= 2500 for c in fake_sarvam.tts_calls)
    assert all(c["model"] == "bulbul:v3" and c["language_code"] == "hi-IN" for c in fake_sarvam.tts_calls)
    assert base64.b64decode(r["audio_b64"]).count(b"ID3fake-mp3-") == r["chunks"]


def test_voice_turn_round_trip(client, fake_sarvam, fresh_db):
    r = client.post("/voice/turn", files={"audio": ("rec.webm", b"\x1aE\xdf\xa3fake", "audio/webm")},
                    data={"history": "[]"})
    assert r.status_code == 200
    body = r.json()
    assert body["transcript"] == "सुनीता जी ने 650 का उधार लिया, शुक्रवार तक देंगे।"
    assert body["reply_text"] == "₹650, Sunita ji, Friday (20 Nov) tak. Sahi hai?"
    assert body["pending_actions"][0]["kind"] == "log_udhaar"
    assert body["audio"]["provider"] == "sarvam" and body["audio"]["audio_b64"]
    assert fake_sarvam.tts_calls[0]["text"] == "650 rupaye, Sunita ji, Friday (20 November) tak. Sahi hai?"
    assert set(body["timings"]) == {"stt_ms", "agent_ms", "tts_ms", "total_ms"}


def test_voice_turn_rejects_empty_and_huge_audio(client, fake_sarvam):
    assert client.post("/voice/turn", files={"audio": ("e.webm", b"", "audio/webm")}).status_code == 422
    big = b"0" * (speech.MAX_AUDIO_BYTES + 1)
    assert client.post("/voice/turn", files={"audio": ("b.webm", big, "audio/webm")}).status_code == 413


def test_voice_turn_silence(client, monkeypatch):
    fake = FakeSarvam(transcript="")
    monkeypatch.setattr(speech, "get_client", lambda: fake)
    body = client.post("/voice/turn", files={"audio": ("s.webm", b"\x1aE\xdf\xa3", "audio/webm")}).json()
    assert body["transcript"] == "" and "Phir se boliye" in body["reply_text"]
