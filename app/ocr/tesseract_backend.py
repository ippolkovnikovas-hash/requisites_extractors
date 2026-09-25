from PIL import Image
import pytesseract
from pytesseract import Output

from app.ocr.base import OcrBackend

_CONFIG_SIMPLE = r"--psm 11 --oem 3 -c preserve_interword_spaces=1"
_CONFIG_STRUCTURED = r"--psm {psm} --oem 3 -c preserve_interword_spaces=1"


class TesseractBackend(OcrBackend):
    supports_psm = True

    def __init__(self, tesseract_cmd: str | None = None) -> None:
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def image_to_text(self, image: Image.Image, lang: str = "rus+eng") -> str:
        return pytesseract.image_to_string(
            image, lang=lang, config=_CONFIG_SIMPLE
        ).strip()

    def image_to_lines(
        self, image: Image.Image, lang: str = "rus+eng", psm: int = 6
    ) -> list[str]:
        """
        Текст построчно. psm — режим сегментации Tesseract:
        6 — единый блок (таблицы-карточки), 4 — колонки, 11 — разрозненный текст.
        """
        data = pytesseract.image_to_data(
            image, lang=lang, config=_CONFIG_STRUCTURED.format(psm=psm),
            output_type=Output.DICT,
        )
        lines: dict[tuple, list[str]] = {}
        n = len(data["text"])
        for i in range(n):
            word = data["text"][i].strip()
            if not word:
                continue
            # line_num нумеруется внутри абзаца — без par_num строки разных абзацев склеиваются
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(word)
        return [" ".join(words) for words in lines.values()]

    def name(self) -> str:
        return "tesseract"
