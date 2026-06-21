import tempfile
from pathlib import Path

from loguru import logger
from pdf2image import convert_from_path
from PIL import Image, ImageFilter, ImageOps

from app.config import settings
from app.core.enums import ExtractorType
from app.core.exceptions import TextExtractionError
from app.ocr.tesseract_backend import TesseractBackend
from app.schemas.extraction import TextExtractionResult


def _preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    image = ImageOps.autocontrast(image, cutoff=2)
    image = image.filter(ImageFilter.SHARPEN)
    return image


def extract_pdf_ocr(path: Path) -> TextExtractionResult:
    backend = TesseractBackend(tesseract_cmd=settings.tesseract_cmd or None)
    warnings: list[str] = []
    pages_text: list[str] = []
    total_pages = 0

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            images = convert_from_path(
                str(path), dpi=300, fmt="png",
                output_folder=tmp_dir,
                poppler_path=settings.poppler_path or None,
            )
            total_pages = len(images)

            for page_num, image in enumerate(images, start=1):
                try:
                    processed = _preprocess_image(image)
                    lines = backend.image_to_lines(processed)
                    text = "\n".join(lines).strip()
                    if text:
                        pages_text.append(f"[Страница {page_num}]\n{text}")
                    else:
                        warnings.append(f"Page {page_num}: OCR returned empty text")
                except Exception as e:
                    warnings.append(f"Page {page_num}: OCR failed — {e}")

    except Exception as e:
        raise TextExtractionError(f"Cannot OCR PDF: {e}", {"path": str(path)})

    full_text = "\n\n".join(pages_text)
    logger.info("PDF OCR done", path=path.name, pages=total_pages, chars=len(full_text))

    return TextExtractionResult(
        text=full_text,
        extractor_used=ExtractorType.TESSERACT,
        ocr_used=True,
        pages=total_pages,
        warnings=warnings,
    )
