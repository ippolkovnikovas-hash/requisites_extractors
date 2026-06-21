"""
Настройка loguru для всего приложения.

Вызывай setup_logging() один раз при старте:
  - в run_cli.py  (CLI)
  - в main.py     (Flask)
"""

import sys
from pathlib import Path

from loguru import logger


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
        format=(
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
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}",
        )

    logger.debug("Logging initialized", level=log_level, file=log_to_file)
