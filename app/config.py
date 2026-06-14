"""
Конфигурация приложения через pydantic-settings.
Читает значения из .env файла и переменных окружения.

Пример .env:
  LLM_PROVIDER=ollama
  OPENAI_API_KEY=none
  OPENAI_BASE_URL=https://api.openai.com/v1
  OPENAI_MODEL=gpt-4o-mini
  OLLAMA_BASE_URL=http://localhost:11434
  OLLAMA_MODEL=qwen2.5:3b
  PROMPT_VERSION=v1
    TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
  LLM_TIMEOUT_SECONDS=120.0
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ─────────────────────────────────────────────────────────────
    llm_provider: str = "mock"           # mock | openai | ollama
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"    # используется в OpenAIClient
    llm_model: str = "gpt-4o-mini"       # алиас для обратной совместимости
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1024
    llm_timeout_seconds: float = 120.0

    # ── Ollama ───────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    # ── Промпт ──────────────────────────────────────────────────────────
    prompt_version: str = "v1"           # v1 | v2 | v3

    # ── OCR ─────────────────────────────────────────────────────────────
    tesseract_cmd: str = ""              # путь к tesseract.exe, пусто = системный PATH
    ocr_backend: str = "tesseract"       # tesseract | easyocr
    ocr_min_text_chars: int = 50

    # ── Файлы ────────────────────────────────────────────────────────────
    max_upload_size_mb: int = 20
    allowed_extensions: list[str] = ["pdf", "docx", "jpg", "jpeg", "png", "tiff"]
    poppler_path: str = ""

    # ── Папки ────────────────────────────────────────────────────────────
    upload_folder: Path = Path("uploads")
    exports_folder: Path = Path("exports")
    processed_folder: Path = Path("processed")

    # ── Flask ────────────────────────────────────────────────────────────
    flask_secret_key: str = "change-me-in-production"
    flask_debug: bool = False
    flask_host: str = "127.0.0.1"
    flask_port: int = 5000

    def ensure_dirs(self) -> None:
        for folder in (self.upload_folder, self.exports_folder, self.processed_folder):
            folder.mkdir(parents=True, exist_ok=True)


settings = Settings()