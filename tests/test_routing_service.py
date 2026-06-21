"""Тесты сервиса маршрутизации документов."""
import pytest
from pathlib import Path
from app.schemas.document import DocumentInput
from app.services.routing_service import detect_document_type
from app.core.enums import DocumentType


def make_doc(**kwargs) -> DocumentInput:
    defaults = dict(
        document_id="test-001",
        original_filename="test.pdf",
        extension="pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        storage_path=Path("tests/fixtures/sample_requisites.pdf"),
        sha256="abc123",
    )
    defaults.update(kwargs)
    return DocumentInput(**defaults)


def test_pdf_text_detected():
    doc = make_doc()
    assert detect_document_type(doc) == DocumentType.PDF_TEXT


def test_pdf_scan_detected_empty_pdf(tmp_path):
    from reportlab.pdfgen import canvas
    empty = tmp_path / "scan.pdf"
    canvas.Canvas(str(empty)).save()
    doc = make_doc(storage_path=empty)
    assert detect_document_type(doc) == DocumentType.PDF_SCAN


def test_docx_by_extension():
    doc = make_doc(
        original_filename="test.docx",
        extension="docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        storage_path=Path("tests/fixtures/sample_requisites.docx"),
    )
    assert detect_document_type(doc) == DocumentType.DOCX


def test_docx_by_mime():
    doc = make_doc(
        original_filename="renamed.bin",
        extension="bin",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        storage_path=Path("tests/fixtures/sample_requisites.docx"),
    )
    assert detect_document_type(doc) == DocumentType.DOCX


def test_image_by_extension():
    doc = make_doc(
        original_filename="scan.jpg",
        extension="jpg",
        mime_type="image/jpeg",
        storage_path=Path("tests/fixtures/sample_requisites.pdf"),
    )
    assert detect_document_type(doc) == DocumentType.IMAGE


def test_image_by_mime():
    doc = make_doc(
        original_filename="scan.bin",
        extension="bin",
        mime_type="image/png",
        storage_path=Path("tests/fixtures/sample_requisites.pdf"),
    )
    assert detect_document_type(doc) == DocumentType.IMAGE


def test_unsupported_type():
    doc = make_doc(
        original_filename="data.csv",
        extension="csv",
        mime_type="text/csv",
    )
    assert detect_document_type(doc) == DocumentType.UNSUPPORTED


def test_pdf_scan_on_broken_file(tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a real pdf")
    doc = make_doc(storage_path=broken)
    assert detect_document_type(doc) == DocumentType.PDF_SCAN
