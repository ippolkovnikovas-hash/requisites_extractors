from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from app.ocr.factory import get_ocr_backend
from app.ocr.image_preprocessing import binarize_otsu, deskew
from app.ocr.numeric_rerun import rerun_numeric_lines
from app.schemas.extraction import TextExtractionResult


def _preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    image = deskew(image)
    w, h = image.size
    image = image.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
    image = ImageOps.autocontrast(image, cutoff=2)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = image.filter(ImageFilter.SHARPEN)
    # Порог подбирается по гистограмме самого изображения (метод Оцу), а не
    # фиксируется заранее — на фото с неравномерным освещением фиксированный
    # порог либо заливал часть кадра чёрным, либо не убирал шум вовсе.
    return binarize_otsu(image)


def extract_image_ocr(path: Path) -> TextExtractionResult:
    backend = get_ocr_backend()
    image = _preprocess_image(Image.open(path))
    lines = rerun_numeric_lines(backend, image)
    text = "\n".join(lines).strip()
    return TextExtractionResult(
        text=text,
        extractor_used=backend.name(),
        ocr_used=True,
        pages=1,
    )
