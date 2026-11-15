"""Environment settings. Every external key is optional; missing keys select offline fallbacks."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

# OpenAI-compatible chat-completions endpoints. Groq is preferred when its key is set.
LLM_PROVIDERS = {
    "groq": "https://api.groq.com/openai/v1",
    "grok": "https://api.x.ai/v1",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    xai_api_key: str = ""
    xai_model: str = "grok-4.7"
    sarvam_api_key: str = ""
    sarvam_tts_speaker: str = "shubh"
    demo_pin: str = "1234"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'vyapar.db').as_posix()}"
    demo_date: str = ""  # YYYY-MM-DD; empty = today (IST)
    demo_now: str = ""  # optional ISO datetime the demo clock starts at after reset
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    enable_scheduler: bool = True
    enable_hardware: bool = False  # Arduino display over USB serial; local demo rig only

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_mode(self) -> str:
        """groq / grok / fallback (rule-based parser)."""
        if self.groq_api_key:
            return "groq"
        if self.xai_api_key:
            return "grok"
        return "fallback"

    @property
    def llm_api_key(self) -> str:
        return {"groq": self.groq_api_key, "grok": self.xai_api_key}.get(self.llm_mode, "")

    @property
    def llm_model(self) -> str:
        return {"groq": self.groq_model, "grok": self.xai_model}.get(self.llm_mode, "rule-based parser")

    @property
    def llm_base_url(self) -> str:
        return LLM_PROVIDERS.get(self.llm_mode, "")

    @property
    def voice_mode(self) -> str:
        return "sarvam" if self.sarvam_api_key else "browser"

    @property
    def messaging_mode(self) -> str:
        """Customer messages are shown as on-screen previews (WhatsApp sending is not enabled)."""
        return "preview"


@lru_cache
def get_settings() -> Settings:
    return Settings()
