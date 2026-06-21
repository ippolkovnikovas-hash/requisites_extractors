from abc import ABC, abstractmethod
from PIL import Image


class OcrBackend(ABC):
    @abstractmethod
    def image_to_text(self, image: Image.Image, lang: str = "rus+eng") -> str:
        ...

    def name(self) -> str:
        return self.__class__.__name__
