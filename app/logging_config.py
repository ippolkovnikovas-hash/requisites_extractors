"""
Настройка loguru для всего приложения.

Вызывай setup_logging() один раз при старте:
  - в run_cli.py  (CLI)
  - в main.py     (Flask)
"""

import sys
from pathlib import Path

from loguru import logger


def _format_with_extra(template: str):
    """
    Дописывает к строке лога поля из `record["extra"]`.

    loguru кладёт kwargs в `extra`, а формат состоял из одного `{message}` —
    поэтому весь структурный контекст (`document_id=`, `fill_rate=`, `chars=`)
    молча пропадал. Фигурные скобки в значениях экранируются: иначе loguru
    примет их за плейсхолдеры и упадёт на форматировании.
    """

    def formatter(record) -> str:
        extra = record["extra"]
        if not extra:
            return template + "\n"
        pairs = " ".join(f"{key}={value}" for key, value in extra.items())
        return template + " | " + pairs.replace("{", "{{").replace("}", "}}") + "\n"

    return formatter


def setup_logging(log_level: str = "INFO", log_to_file: bool = True) -> None:
    """
    Настраивает loguru:
      - консоль: цветной вывод, уровень INFO
      - файл:    logs/app.log, ротация 10 MB, хранение 7 дней, уровень DEBUG
    """
    # Убираем дефолтный хендлер loguru
    logger.remove()

    # --- Консоль ---
    logger.add(
        sys.stderr,
        level=log_level,
        colorize=True,
        format=_format_with_extra(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
    )

    # --- Файл ---
    if log_to_file:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        logger.add(
            logs_dir / "app.log",
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
            encoding="utf-8",
            format=_format_with_extra(
                "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}"
            ),
        )

    logger.debug("Logging initialized", level=log_level, file=log_to_file)
