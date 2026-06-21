"""Тесты PDF text-экстрактора."""
import pytest
from pathlib import Path
from app.extractors.pdf_text_extractor import extract_pdf_text
from app.core.exceptions import TextExtractionError
from app.core.enums import ExtractorType

FIXTURE = Path("tests/fixtures/sample_requisites.pdf")


def test_extracts_text_from_pdf():
    result = extract_pdf_text(FIXTURE)
    assert result.text
    assert len(result.text) > 50


def test_contains_inn():
    result = extract_pdf_text(FIXTURE)
    assert "7744012347" in result.text


def test_contains_ogrn():
    result = extract_pdf_text(FIXTURE)
    assert "1027700123450" in result.text


def test_contains_bik():
    result = extract_pdf_text(FIXTURE)
    assert "044525225" in result.text


def test_extractor_type():
    result = extract_pdf_text(FIXTURE)
    assert result.extractor_used == ExtractorType.PDFPLUMBER


def test_ocr_not_used():
    result = extract_pdf_text(FIXTURE)
    assert result.ocr_used is False


def test_pages_count():
    result = extract_pdf_text(FIXTURE)
    assert result.pages == 1


def test_no_scan_warning_on_valid_pdf():
    result = extract_pdf_text(FIXTURE)
    scan_warnings = [w for w in result.warnings if "scan" in w.lower()]
    assert scan_warnings == []


def test_raises_on_missing_file():
    with pytest.raises(TextExtractionError):
        extract_pdf_text(Path("tests/fixtures/nonexistent.pdf"))


def test_scan_warning_on_empty_pdf(tmp_path):
    from reportlab.pdfgen import canvas
    empty_pdf = tmp_path / "empty.pdf"
    c = canvas.Canvas(str(empty_pdf))
    c.save()
    result = extract_pdf_text(empty_pdf)
    assert any("scan" in w.lower() or "too small" in w.lower() for w in result.warnings)


def test_multipage_pdf():
    result = extract_pdf_text(Path("tests/fixtures/sample_two_pages.pdf"))
    assert result.pages == 2
    assert result.text.count("[Страница") == 2
    assert "7744012347" in result.text


def test_table_extraction_error_adds_warning(tmp_path, monkeypatch):
    import pdfplumber
    original_open = pdfplumber.open

    class FakePage:
        def extract_text(self, **kw): return "ИНН: 7744012347"
        def extract_tables(self): raise RuntimeError("table parse error")

    class FakePDF:
        pages = [FakePage()]
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(pdfplumber, "open", lambda *a, **kw: FakePDF())
    result = extract_pdf_text(tmp_path / "fake.pdf")
    assert any("table extraction failed" in w for w in result.warnings)
    assert "7744012347" in result.text


def test_table_extraction_error_adds_warning(tmp_path, monkeypatch):
    import pdfplumber
    original_open = pdfplumber.open

    class FakePage:
        def extract_text(self, **kw): return "ИНН: 7744012347"
        def extract_tables(self): raise RuntimeError("table parse error")

    class FakePDF:
        pages = [FakePage()]
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(pdfplumber, "open", lambda *a, **kw: FakePDF())
    result = extract_pdf_text(tmp_path / "fake.pdf")
    assert any("table extraction failed" in w for w in result.warnings)
    assert "7744012347" in result.text
