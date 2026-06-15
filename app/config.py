from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "app" / "static" / "uploads"


class Settings:
    app_name: str = "QalaPulse AI"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./qalapulse.db")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    deepseek_api_key: str | None = os.getenv("DEEPSEEK_API_KEY")
    enable_llm: bool = os.getenv("ENABLE_LLM", "false").lower() in {"1", "true", "yes"}


settings = Settings()
