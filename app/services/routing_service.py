"""
Определение типа документа и выбор стратегии обработки.

Порядок проверки:
  1. Расширение файла → быстрый первичный маршрут.
  2. MIME-тип → уточнение (защита от переименованных файлов).
  3. Для PDF — эвристика: есть ли текстовый слой?
     Если символов < OCR_MIN_TEXT_CHARS → PDF_SCAN.

Результат записывается в doc.doc_type (DocumentType enum).
"""

from pathlib import Path

import pdfplumber
from loguru import logger

from app.config import settings
from app.core.constants import (
    DOCX_EXTENSION,
    IMAGE_EXTENSIONS,
    PDF_EXTENSION,
)
from app.core.enums import DocumentType
from app.schemas.document import DocumentInput


def detect_document_type(doc: DocumentInput) -> DocumentType:
    """
    Определяет DocumentType по расширению, MIME и (для PDF) содержимому.
    Не бросает исключений — при неизвестном типе возвращает UNSUPPORTED.
    """
    ext = doc.extension.lower().strip(".")
    mime = doc.mime_type.lower()

    # --- DOCX ---
    if ext == DOCX_EXTENSION or "wordprocessingml" in mime:
        logger.debug("Routing → DOCX", file=doc.original_filename)
        return DocumentType.DOCX

    # --- Изображения ---
    if ext in IMAGE_EXTENSIONS or mime.startswith("image/"):
        logger.debug("Routing → IMAGE", file=doc.original_filename)
        return DocumentType.IMAGE

    # --- PDF: текстовый или скан? ---
    if ext == PDF_EXTENSION or mime == "application/pdf":
        doc_type = _detect_pdf_type(doc.storage_path)
        logger.debug("Routing → PDF", subtype=doc_type, file=doc.original_filename)
        return doc_type

    logger.warning(
        "Unsupported file type",
        ext=ext,
        mime=mime,
        file=doc.original_filename,
    )
    return DocumentType.UNSUPPORTED


def _detect_pdf_type(file_path: Path) -> DocumentType:
    """
    Открывает PDF и считает символы на первых 3 страницах.
    Если меньше порога — скан.
    """
    try:
        with pdfplumber.open(str(file_path)) as pdf:
            sample_pages = pdf.pages[:3]
            total_chars = 0
            for page in sample_pages:
                text = page.extract_text()
                if text:
                    total_chars += len(text.strip())

        if total_chars < settings.ocr_min_text_chars:
            logger.debug(
                "PDF detected as scan",
                chars=total_chars,
                threshold=settings.ocr_min_text_chars,
            )
            return DocumentType.PDF_SCAN

        return DocumentType.PDF_TEXT

    except Exception as e:
        logger.warning("PDF type detection failed, assuming scan", error=str(e))
        return DocumentType.PDF_SCAN
