import pytesseract
from PIL import Image
from pytesseract import Output

from app.ocr.base import OcrBackend

_CONFIG_SIMPLE = r"--psm 11 --oem 3 -c preserve_interword_spaces=1"
_CONFIG_STRUCTURED = r"--psm 6 --oem 3 -c preserve_interword_spaces=1"


class TesseractBackend(OcrBackend):
    def __init__(self, tesseract_cmd: str | None = None) -> None:
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def image_to_text(self, image: Image.Image, lang: str = "rus+eng") -> str:
        return pytesseract.image_to_string(
            image, lang=lang, config=_CONFIG_SIMPLE
        ).strip()

    def image_to_lines_with_word_boxes(
        self, image: Image.Image, lang: str = "rus+eng"
    ) -> list[tuple[str, list[tuple[str, tuple[int, int, int, int]]]]]:
        data = pytesseract.image_to_data(
            image,
            lang=lang,
            config=_CONFIG_STRUCTURED,
            output_type=Output.DICT,
        )
        lines: dict[tuple, list[tuple[str, tuple[int, int, int, int]]]] = {}
        n = len(data["text"])
        for i in range(n):
            word = data["text"][i].strip()
            if not word:
                continue
            # Полный адрес строки. `line_num` нумеруется внутри параграфа, а
            # не внутри блока: без `par_num` строки разных параграфов с
            # одинаковым номером сливались в одну, и документ схлопывался в
            # пару строк вместо полутора десятков.
            key = (
                data["page_num"][i],
                data["block_num"][i],
                data["par_num"][i],
                data["line_num"][i],
            )
            left = data["left"][i]
            top = data["top"][i]
            right = left + data["width"][i]
            bottom = top + data["height"][i]
            lines.setdefault(key, []).append((word, (left, top, right, bottom)))
        return [
            (" ".join(word for word, _ in words), words) for words in lines.values()
        ]

    def image_to_lines_with_boxes(
        self, image: Image.Image, lang: str = "rus+eng"
    ) -> list[tuple[str, tuple[int, int, int, int]]]:
        result: list[tuple[str, tuple[int, int, int, int]]] = []
        for text, words in self.image_to_lines_with_word_boxes(image, lang=lang):
            boxes = [box for _, box in words]
            left = min(b[0] for b in boxes)
            top = min(b[1] for b in boxes)
            right = max(b[2] for b in boxes)
            bottom = max(b[3] for b in boxes)
            result.append((text, (left, top, right, bottom)))
        return result

    def image_to_lines(self, image: Image.Image, lang: str = "rus+eng") -> list[str]:
        return [text for text, _ in self.image_to_lines_with_boxes(image, lang=lang)]

    def name(self) -> str:
        return "tesseract"
