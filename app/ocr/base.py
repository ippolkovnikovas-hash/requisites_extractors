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

    def image_to_lines_with_boxes(
        self, image: Image.Image, lang: str = "rus+eng"
    ) -> list[tuple[str, tuple[int, int, int, int] | None]]:
        """
        Строки с прямоугольниками, в порядке появления.

        Базовая реализация не даёт геометрии (`bbox=None`): бэкенд,
        переопределяющий `image_to_lines`, по-прежнему работает, но повторное
        распознавание регионов для него невозможно. Tesseract отдаёт реальные
        bbox.
        """
        return [(line, None) for line in self.image_to_lines(image, lang=lang)]

    def image_to_lines_with_word_boxes(
        self, image: Image.Image, lang: str = "rus+eng"
    ) -> list[tuple[str, list[tuple[str, tuple[int, int, int, int]]]]]:
        """
        Строки со словами и их прямоугольниками, в порядке появления.

        Геометрия отдельных слов нужна, чтобы перераспознать только слово с
        числом, не задев соседнее слово-метку в том же bbox строки (whitelist
        на весь bbox строки заставляет Tesseract впихивать буквы метки в
        цифры — источник порчи данных, найденный реальным замером
        05.09.2026). Базовая реализация не даёт геометрии слов (пустой
        список) — таргетный rerun для такого бэкенда невозможен.
        """
        return [(line, []) for line in self.image_to_lines(image, lang=lang)]

    def name(self) -> str:
        return self.__class__.__name__
