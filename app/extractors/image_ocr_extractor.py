from pathlib import Path

import pytesseract
from PIL import Image, ImageFilter, ImageOps

from app.config import settings
from app.schemas.extraction import TextExtractionResult

TESSERACT_CONFIG = r"--psm 11 --oem 3 -c preserve_interword_spaces=1"


def _preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")

    w, h = image.size
    image = image.resize((w * 2, h * 2), Image.Resampling.LANCZOS)

    image = ImageOps.autocontrast(image, cutoff=2)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = image.filter(ImageFilter.SHARPEN)

    image = image.point(lambda x: 0 if x < 170 else 255, mode="1")
    return image.convert("L")


def extract_image_ocr(path: Path) -> TextExtractionResult:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    image = Image.open(path)
    image = _preprocess_image(image)

    text = pytesseract.image_to_string(
        image,
        lang="rus+eng",
        config=TESSERACT_CONFIG,
    ).strip()

    return TextExtractionResult(
        text=text,
        extractor_used="tesseract",
        ocr_used=True,
        pages=1,
    )
