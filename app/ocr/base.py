"""
Интерфейс OCR-бэкенда.

`image_to_lines()` входит в контракт, а не живёт в одной конкретной реализации:
экстракторы пользуются именно им, и если бы метод был только у Tesseract,
переключение `OCR_BACKEND` падало бы в рантайме.

Обязателен к реализации только `image_to_text()`. Построчный разбор имеет
разумную реализацию по умолчанию — бэкенд переопределяет её, если умеет отдавать
структуру точнее (как Tesseract через `image_to_data`).
"""

from abc import ABC, abstractmethod

from PIL import Image


class OcrBackend(ABC):
    @abstractmethod
    def image_to_text(self, image: Image.Image, lang: str = "rus+eng") -> str: ...

    def image_to_lines(self, image: Image.Image, lang: str = "rus+eng") -> list[str]:
        """Строки распознанного текста без пустых."""
        text = self.image_to_text(image, lang=lang)
        return [line.strip() for line in text.splitlines() if line.strip()]

    def name(self) -> str:
        return self.__class__.__name__
