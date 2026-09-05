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

    def image_to_lines_with_boxes(
        self, image: Image.Image, lang: str = "rus+eng"
    ) -> list[tuple[str, tuple[int, int, int, int]]]:
        data = pytesseract.image_to_data(
            image,
            lang=lang,
            config=_CONFIG_STRUCTURED,
            output_type=Output.DICT,
        )
        lines: dict[tuple, list[str]] = {}
        boxes: dict[tuple, tuple[int, int, int, int]] = {}
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
            lines.setdefault(key, []).append(word)
            left = data["left"][i]
            top = data["top"][i]
            right = left + data["width"][i]
            bottom = top + data["height"][i]
            if key in boxes:
                prev = boxes[key]
                boxes[key] = (
                    min(prev[0], left),
                    min(prev[1], top),
                    max(prev[2], right),
                    max(prev[3], bottom),
                )
            else:
                boxes[key] = (left, top, right, bottom)
        return [(" ".join(lines[key]), boxes[key]) for key in lines]

    def image_to_lines(self, image: Image.Image, lang: str = "rus+eng") -> list[str]:
        return [text for text, _ in self.image_to_lines_with_boxes(image, lang=lang)]

    def recognize_region(
        self,
        image: Image.Image,
        bbox: tuple[int, int, int, int],
        whitelist: str,
        lang: str = "rus+eng",
    ) -> str:
        """Повторный прогон Tesseract на обрезанном регионе с `char_whitelist`."""
        left, top, right, bottom = bbox
        region = image.crop((left, top, right, bottom))
        config = f"{_CONFIG_STRUCTURED} -c tessedit_char_whitelist={whitelist}"
        return pytesseract.image_to_string(region, lang=lang, config=config).strip()

    def name(self) -> str:
        return "tesseract"
