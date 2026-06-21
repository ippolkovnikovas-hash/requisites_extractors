from PIL import Image
import numpy as np

from app.ocr.base import OcrBackend


class EasyOcrBackend(OcrBackend):
    def __init__(self, langs: list[str] | None = None) -> None:
        import easyocr
        self._reader = easyocr.Reader(langs or ["ru", "en"], gpu=False)

    def image_to_text(self, image: Image.Image, lang: str = "rus+eng") -> str:
        img_array = np.array(image)
        results = self._reader.readtext(img_array, detail=0, paragraph=True)
        return "\n".join(results)

    def name(self) -> str:
        return "easyocr"
