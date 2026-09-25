"""
Выбор OCR-бэкенда по настройке OCR_BACKEND.

Новый бэкенд (например, облачный) — класс-наследник OcrBackend и ветка здесь;
экстракторы изображений и PDF-сканов менять не нужно.
name() бэкенда должен совпадать со значением ExtractorType (app/core/enums.py).

Облачный бэкенд оборачивается в FallbackOcrBackend: при ошибке сети/API
страница распознаётся локальным Tesseract.
"""

from loguru import logger
from PIL import Image

from app.config import settings
from app.ocr.base import OcrBackend


def _tesseract() -> OcrBackend:
    from app.ocr.tesseract_backend import TesseractBackend
    return TesseractBackend(tesseract_cmd=settings.tesseract_cmd or None)


class FallbackOcrBackend(OcrBackend):
    """Облачный OCR с запасным локальным: сбой облака не роняет обработку документа."""

    supports_psm = False
    needs_preprocessing = False

    def __init__(self, primary: OcrBackend, fallback_factory=_tesseract) -> None:
        self._primary = primary
        self._fallback_factory = fallback_factory
        self._fallback: OcrBackend | None = None
        self.fallback_used = False

    def image_to_lines(self, image: Image.Image, lang: str = "rus+eng", psm: int = 6) -> list[str]:
        try:
            return self._primary.image_to_lines(image, lang)
        except Exception as e:
            logger.warning("Cloud OCR failed, falling back to Tesseract", reason=str(e))
            from app.extractors.image_ocr_extractor import _preprocess_image

            if self._fallback is None:
                self._fallback = self._fallback_factory()
            self.fallback_used = True
            return self._fallback.image_to_lines(_preprocess_image(image), lang)

    def image_to_text(self, image: Image.Image, lang: str = "rus+eng") -> str:
        return "\n".join(self.image_to_lines(image, lang))

    def name(self) -> str:
        return (self._fallback or self._primary).name() if self.fallback_used else self._primary.name()


def get_ocr_backend() -> OcrBackend:
    backend = settings.ocr_backend.lower()

    if backend == "easyocr":
        from app.ocr.easyocr_backend import EasyOcrBackend
        return EasyOcrBackend()

    if backend == "yandex":
        from app.ocr.yandex_vision_backend import YandexVisionBackend
        try:
            return FallbackOcrBackend(YandexVisionBackend())
        except Exception as e:
            logger.warning("Yandex Vision unavailable, using tesseract", reason=str(e))
            return _tesseract()

    if backend != "tesseract":
        logger.warning("Unknown OCR_BACKEND={}, falling back to tesseract", backend)

    return _tesseract()
