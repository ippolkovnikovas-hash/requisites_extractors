"""
Конфигурация приложения через pydantic-settings.
Читает значения из .env файла и переменных окружения.

Пример .env:
  LLM_PROVIDER=ollama
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
    # Только локальные провайдеры: ollama — локальный endpoint, mock — тесты/CI.
    # Внешние LLM-сервисы в проекте запрещены (см. CLAUDE.md, раздел «Приватность»).
    llm_provider: str = "mock"  # mock | ollama
    llm_timeout_seconds: float = 120.0

    # ── Ollama ───────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    # ── Промпт ──────────────────────────────────────────────────────────
    prompt_version: str = "v1"

    # Профиль промпта для распознанного текста. У OCR своя специфика — цифры с
    # пробелами внутри, слитные строки, подмены символов, — и профиль `image`
    # написан именно под неё.
    ocr_prompt_version: str = "image"  # v1 | v2 | v3

    # ── OCR ─────────────────────────────────────────────────────────────
    tesseract_cmd: str = ""  # путь к tesseract.exe, пусто = системный PATH
    ocr_backend: str = "tesseract"  # tesseract | easyocr
    ocr_min_text_chars: int = 50

    # ── Файлы ────────────────────────────────────────────────────────────
    max_upload_size_mb: int = 20
    allowed_extensions: list[str] = ["pdf", "docx", "jpg", "jpeg", "png", "tiff"]
    poppler_path: str = ""

    # ── Папки ────────────────────────────────────────────────────────────
    upload_folder: Path = Path("uploads")
    exports_folder: Path = Path("exports")
    processed_folder: Path = Path("processed")

    # ── Артефакты ────────────────────────────────────────────────────────
    # По умолчанию pipeline не оставляет на диске ни сырой текст, ни
    # результаты: реквизиты не должны переживать обработку (CLAUDE.md).
    # Включается осознанно — для CLI и пакетной обработки, где отчёты нужны.
    persist_artifacts: bool = False

    # ── Flask ────────────────────────────────────────────────────────────
    flask_secret_key: str = "change-me-in-production"
    flask_debug: bool = False
    flask_host: str = "127.0.0.1"
    flask_port: int = 5000

    def ensure_dirs(self) -> None:
        for folder in (self.upload_folder, self.exports_folder, self.processed_folder):
            folder.mkdir(parents=True, exist_ok=True)


settings = Settings()
