"""
Тесты диспетчера извлечения текста.

Проверяется только маршрутизация: какой экстрактор вызывается для какого типа
документа. Сами экстракторы подменяются — реальные OCR и pdfplumber здесь не
нужны и только замедлили бы прогон.
"""

import pytest

from app.core.enums import DocumentType
from app.core.exceptions import UnsupportedFileTypeError
from app.schemas.document import DocumentInput
from app.schemas.extraction import TextExtractionResult
from app.services.text_extraction_service import extract_text


def _document(doc_type: DocumentType, tmp_path) -> DocumentInput:
    path = tmp_path / "doc.bin"
    path.write_bytes(b"stub")
    doc = DocumentInput(
        document_id="extract1",
        original_filename="doc.bin",
        extension="bin",
        mime_type="application/octet-stream",
        size_bytes=4,
        storage_path=path,
        sha256="0" * 64,
    )
    doc.doc_type = doc_type
    return doc


def _stub_result(marker: str) -> TextExtractionResult:
    return TextExtractionResult(
        text=marker,
        extractor_used="pdfplumber",
        ocr_used=False,
        pages=1,
    )


@pytest.mark.parametrize(
    "doc_type,module_path,function_name",
    [
        (DocumentType.DOCX, "app.extractors.docx_extractor", "extract_docx"),
        (
            DocumentType.PDF_TEXT,
            "app.extractors.pdf_text_extractor",
            "extract_pdf_text",
        ),
        (DocumentType.PDF_SCAN, "app.extractors.pdf_ocr_extractor", "extract_pdf_ocr"),
        (
            DocumentType.IMAGE,
            "app.extractors.image_ocr_extractor",
            "extract_image_ocr",
        ),
    ],
)
def test_dispatches_to_matching_extractor(
    doc_type, module_path, function_name, tmp_path, monkeypatch
):
    import importlib

    module = importlib.import_module(module_path)
    monkeypatch.setattr(
        module, function_name, lambda path: _stub_result(f"called:{function_name}")
    )

    result = extract_text(_document(doc_type, tmp_path))

    assert result.text == f"called:{function_name}"


def test_passes_storage_path_to_extractor(tmp_path, monkeypatch):
    import app.extractors.docx_extractor as module

    received = {}

    def fake(path):
        received["path"] = path
        return _stub_result("ok")

    monkeypatch.setattr(module, "extract_docx", fake)
    doc = _document(DocumentType.DOCX, tmp_path)

    extract_text(doc)

    assert received["path"] == doc.storage_path


def test_unsupported_doc_type_raises(tmp_path):
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        extract_text(_document(DocumentType.UNSUPPORTED, tmp_path))

    assert "doc.bin" in str(exc_info.value.details)


def test_unknown_doc_type_raises(tmp_path):
    """Значение вне enum тоже должно приводить к явной ошибке, а не к None."""
    doc = _document(DocumentType.DOCX, tmp_path)
    doc.doc_type = "something_new"

    with pytest.raises(UnsupportedFileTypeError):
        extract_text(doc)
