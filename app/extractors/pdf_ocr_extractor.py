"""
OCR-извлечение текста из сканированных PDF.

Стратегия:
  1. Конвертируем страницы PDF в изображения через pdf2image.
  2. Для каждой страницы применяем препроцессинг изображения.
  3. Прогоняем страницу через pytesseract.
  4. Склеиваем текст всех страниц в единый результат.
"""

import tempfile
from pathlib import Path

import pytesseract
from loguru import logger
from pdf2image import convert_from_path
from PIL import Image, ImageFilter, ImageOps

from app.config import settings
from app.core.enums import ExtractorType
from app.core.exceptions import TextExtractionError
from app.schemas.extraction import TextExtractionResult

TESSERACT_CONFIG = r"--psm 11 --oem 3 -c preserve_interword_spaces=1"


def _preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    image = ImageOps.autocontrast(image, cutoff=2)
    image = image.filter(ImageFilter.SHARPEN)
    return image


def extract_pdf_ocr(path: Path) -> TextExtractionResult:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    warnings: list[str] = []
    pages_text: list[str] = []

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            images = convert_from_path(
                str(path),
                dpi=300,
                fmt="png",
                output_folder=tmp_dir,
                poppler_path=settings.poppler_path or None,
            )

            total_pages = len(images)

            for page_num, image in enumerate(images, start=1):
                try:
                    processed = _preprocess_image(image)
                    text = pytesseract.image_to_string(
                        processed,
                        lang="rus+eng",
                        config=TESSERACT_CONFIG,
                    ).strip()

                    if text:
                        pages_text.append(f"[Страница {page_num}]\n{text}")
                    else:
                        warnings.append(f"Page {page_num}: OCR returned empty text")

                except Exception as page_error:
                    warnings.append(f"Page {page_num}: OCR failed — {page_error}")

    except Exception as e:
        raise TextExtractionError(
            f"Cannot OCR PDF: {e}",
            {"path": str(path)},
        )

    full_text = "\n\n".join(pages_text)

    logger.info(
        "PDF OCR extraction done",
        path=path.name,
        pages=total_pages if 'total_pages' in locals() else 0,
        chars=len(full_text),
        warnings=len(warnings),
    )

    return TextExtractionResult(
        text=full_text,
        extractor_used=ExtractorType.TESSERACT,
        ocr_used=True,
        pages=total_pages if 'total_pages' in locals() else len(pages_text),
        warnings=warnings,
    )
