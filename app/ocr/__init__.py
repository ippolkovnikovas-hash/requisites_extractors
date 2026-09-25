"""
Выбор OCR-бэкенда по настройке OCR_BACKEND.

Новый бэкенд (например, облачный) — класс-наследник OcrBackend и ветка здесь;
экстракторы изображений и PDF-сканов менять не нужно.
name() бэкенда должен совпадать со значением ExtractorType (app/core/enums.py).
"""

from app.config import settings
from app.ocr.base import OcrBackend


def get_ocr_backend() -> OcrBackend:
    backend = settings.ocr_backend.lower()

    if backend == "easyocr":
        from app.ocr.easyocr_backend import EasyOcrBackend
        return EasyOcrBackend()

    if backend != "tesseract":
        from loguru import logger
        logger.warning("Unknown OCR_BACKEND={}, falling back to tesseract", backend)

    from app.ocr.tesseract_backend import TesseractBackend
    return TesseractBackend(tesseract_cmd=settings.tesseract_cmd or None)
