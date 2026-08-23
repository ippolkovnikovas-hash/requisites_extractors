"""
Выбор OCR-бэкенда по настройке `OCR_BACKEND`.

До появления этой фабрики настройка ни на что не влияла: оба экстрактора
импортировали `TesseractBackend` напрямую, а значение из `.env` только
печаталось в `run_cli.py info`.

Импорт реализаций ленивый: `easyocr` — опциональная зависимость, и модуль с ним
не должен требоваться тем, кто им не пользуется.
"""

from app.config import settings
from app.core.exceptions import ConfigError
from app.ocr.base import OcrBackend

TESSERACT = "tesseract"
EASYOCR = "easyocr"

SUPPORTED = (TESSERACT, EASYOCR)


def get_ocr_backend(name: str | None = None) -> OcrBackend:
    """
    Возвращает бэкенд по имени; `None` — взять из настроек.

    Неизвестное имя — ошибка конфигурации, а не тихий откат на Tesseract:
    пользователь, указавший бэкенд, должен узнать, что его выбор не сработал.
    """
    backend_name = (name or settings.ocr_backend or TESSERACT).lower()

    if backend_name == TESSERACT:
        from app.ocr.tesseract_backend import TesseractBackend

        return TesseractBackend(tesseract_cmd=settings.tesseract_cmd or None)

    if backend_name == EASYOCR:
        import app.ocr.easyocr_backend as easyocr_module

        return easyocr_module.EasyOcrBackend()

    raise ConfigError(
        f"Неизвестный OCR_BACKEND={backend_name!r}. "
        f"Допустимые значения: {', '.join(SUPPORTED)}.",
        {"backend": backend_name, "supported": list(SUPPORTED)},
    )
