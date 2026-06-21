from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from app.config import settings
from app.ocr.tesseract_backend import TesseractBackend
from app.schemas.extraction import TextExtractionResult


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
    backend = TesseractBackend(tesseract_cmd=settings.tesseract_cmd or None)
    image = _preprocess_image(Image.open(path))
    lines = backend.image_to_lines(image)
    text = "\n".join(lines).strip()
    return TextExtractionResult(
        text=text,
        extractor_used="tesseract",
        ocr_used=True,
        pages=1,
    )
