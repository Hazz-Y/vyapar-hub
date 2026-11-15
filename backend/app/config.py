"""Environment settings. Every external key is optional; missing keys select offline fallbacks."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    xai_api_key: str = ""
    xai_model: str = "grok-4.7"
    sarvam_api_key: str = ""
    sarvam_tts_speaker: str = "shubh"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_api_version: str = "v23.0"
    demo_pin: str = "1234"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'vyapar.db').as_posix()}"
    demo_date: str = ""  # YYYY-MM-DD; empty = today (IST)
    demo_now: str = ""  # optional ISO datetime the demo clock starts at after reset
    demo_customer_phone: str = ""  # Sunita ji's number for a live WhatsApp demo (must be allowlisted)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    enable_scheduler: bool = True

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_mode(self) -> str:
        return "grok" if self.xai_api_key else "fallback"

    @property
    def voice_mode(self) -> str:
        return "sarvam" if self.sarvam_api_key else "browser"

    @property
    def whatsapp_mode(self) -> str:
        return "whatsapp" if (self.whatsapp_access_token and self.whatsapp_phone_number_id) else "preview"


@lru_cache
def get_settings() -> Settings:
    return Settings()
