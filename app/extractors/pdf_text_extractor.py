"""
Извлечение текста из цифровых (не сканированных) PDF через pdfplumber.

Стратегия:
  1. Пробуем извлечь текст с каждой страницы через pdfplumber.
  2. Если суммарное число символов < OCR_MIN_TEXT_CHARS — документ считается
     scan-like, возвращаем пустой результат с флагом is_scan_like=True в warnings.
  3. Таблицы на странице находятся заранее и извлекаются структурно
     (`" | "`-разделённые ячейки), а их прямоугольники исключаются из обычного
     текста — иначе `extract_text()` уже включает содержимое ячеек в поток
     чтения, и оно попадало бы в результат дважды: один раз как проза, второй
     раз как табличный блок.
"""

from pathlib import Path

import pdfplumber
from loguru import logger

from app.config import settings
from app.core.enums import ExtractorType
from app.core.exceptions import TextExtractionError
from app.schemas.extraction import TextExtractionResult


def extract_pdf_text(file_path: Path) -> TextExtractionResult:
    warnings: list[str] = []
    pages_text: list[str] = []

    try:
        with pdfplumber.open(str(file_path)) as pdf:
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                page_parts: list[str] = []

                # --- Таблицы находятся заранее: их прямоугольники нужно
                # исключить из обычного текста, иначе ячейки попадут в
                # результат дважды ---
                tables = []
                try:
                    tables = page.find_tables()
                except Exception as te:
                    warnings.append(f"Page {page_num}: table extraction failed — {te}")

                # --- Обычный текст страницы, за вычетом области таблиц ---
                text_source = page
                for table in tables:
                    text_source = text_source.outside_bbox(table.bbox)

                raw_text = text_source.extract_text(x_tolerance=3, y_tolerance=3)
                if raw_text:
                    page_parts.append(raw_text.strip())

                # --- Структурные блоки таблиц ---
                for table in tables:
                    table_lines = []
                    for row in table.extract():
                        cells = [str(cell).strip() for cell in row if cell is not None]
                        if any(cells):
                            table_lines.append(" | ".join(cells))
                    if table_lines:
                        page_parts.append("\n".join(table_lines))

                if page_parts:
                    pages_text.append(
                        f"[Страница {page_num}]\n" + "\n".join(page_parts)
                    )

    except Exception as e:
        raise TextExtractionError(f"Cannot open PDF: {e}", {"path": str(file_path)})

    full_text = "\n\n".join(pages_text)
    char_count = len(full_text.strip())

    # --- Определяем скан ---
    if char_count < settings.ocr_min_text_chars:
        warnings.append(
            f"PDF text layer too small ({char_count} chars < {settings.ocr_min_text_chars}). "
            "Likely a scanned PDF — use OCR extractor instead."
        )
        logger.info(
            "PDF looks like scan",
            path=file_path.name,
            chars=char_count,
            threshold=settings.ocr_min_text_chars,
        )

    logger.debug(
        "PDF text extraction done",
        path=file_path.name,
        pages=total_pages,
        chars=char_count,
    )

    return TextExtractionResult(
        text=full_text,
        extractor_used=ExtractorType.PDFPLUMBER,
        pages=total_pages,
        ocr_used=False,
        warnings=warnings,
    )
