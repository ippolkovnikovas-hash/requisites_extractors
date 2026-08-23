"""
OCR-бэкенд на EasyOCR.

Зависимость опциональная: `easyocr` тянет за собой torch (~500 МБ), а нужен он
далеко не всем — по умолчанию используется Tesseract. Поэтому пакет вынесен в
`requirements/easyocr.txt`, а импорты сделаны ленивыми: модуль можно
импортировать и без установленного easyocr, ошибка возникнет только при
попытке создать бэкенд, и будет она понятной.
"""

from PIL import Image

from app.ocr.base import OcrBackend

_INSTALL_HINT = (
    "Бэкенд easyocr требует дополнительных зависимостей. "
    "Установите их: pip install -r requirements/easyocr.txt"
)


class EasyOcrBackend(OcrBackend):
    def __init__(self, langs: list[str] | None = None) -> None:
        try:
            import easyocr
        except ImportError as e:  # pragma: no cover - зависит от окружения
            raise ImportError(_INSTALL_HINT) from e

        self._reader = easyocr.Reader(langs or ["ru", "en"], gpu=False)

    def image_to_text(self, image: Image.Image, lang: str = "rus+eng") -> str:
        import numpy as np

        img_array = np.array(image)
        results = self._reader.readtext(img_array, detail=0, paragraph=True)
        return "\n".join(results)

    def name(self) -> str:
        return "easyocr"
