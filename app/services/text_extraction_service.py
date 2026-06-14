"""
Фасад извлечения текста.

Принимает DocumentInput с уже определённым doc_type,
выбирает нужный экстрактор и возвращает TextExtractionResult.

Добавление нового формата — только здесь и в extractors/.
"""

from loguru import logger

from app.schemas.document import DocumentInput
from app.schemas.extraction import TextExtractionResult
from app.core.enums import DocumentType
from app.core.exceptions import UnsupportedFileTypeError


def extract_text(doc: DocumentInput) -> TextExtractionResult:
    """
    Диспетчер: выбирает экстрактор по doc.doc_type.
    Все экстракторы импортируются лениво — тяжёлые зависимости
    (tesseract, pdf2image) не грузятся если не нужны.
    """
    logger.info(
        "Extracting text",
        document_id=doc.document_id,
        doc_type=doc.doc_type,
        file=doc.original_filename,
    )

    match doc.doc_type:

        case DocumentType.DOCX:
            from app.extractors.docx_extractor import extract_docx
            return extract_docx(doc.storage_path)

        case DocumentType.PDF_TEXT:
            from app.extractors.pdf_text_extractor import extract_pdf_text
            return extract_pdf_text(doc.storage_path)

        case DocumentType.PDF_SCAN:
            from app.extractors.pdf_ocr_extractor import extract_pdf_ocr
            return extract_pdf_ocr(doc.storage_path)

        case DocumentType.IMAGE:
            from app.extractors.image_ocr_extractor import extract_image_ocr
            return extract_image_ocr(doc.storage_path)

        case DocumentType.UNSUPPORTED | _:
            raise UnsupportedFileTypeError(
                f"No extractor for doc_type={doc.doc_type}",
                {"file": doc.original_filename},
            )