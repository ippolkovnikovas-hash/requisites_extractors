from abc import ABC, abstractmethod

from PIL import Image


class OcrBackend(ABC):
    # Поддерживает ли бэкенд режимы сегментации Tesseract (psm) — нужны для доп. проходов
    supports_psm: bool = False

    @abstractmethod
    def image_to_text(self, image: Image.Image, lang: str = "rus+eng") -> str:
        ...

    def image_to_lines(
        self, image: Image.Image, lang: str = "rus+eng", psm: int = 6
    ) -> list[str]:
        """По умолчанию — построчное разбиение image_to_text; psm игнорируется."""
        return [line for line in self.image_to_text(image, lang).splitlines() if line.strip()]

    def name(self) -> str:
        return self.__class__.__name__
