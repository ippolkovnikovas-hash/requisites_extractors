"""Тесты DOCX-экстрактора."""
import pytest
from pathlib import Path
from app.extractors.docx_extractor import extract_docx
from app.core.exceptions import TextExtractionError

FIXTURE = Path("tests/fixtures/sample_requisites.docx")


def test_extracts_text_from_docx():
    result = extract_docx(FIXTURE)
    assert result.text
    assert len(result.text) > 50


def test_contains_inn():
    result = extract_docx(FIXTURE)
    assert "7744012347" in result.text


def test_contains_ogrn():
    result = extract_docx(FIXTURE)
    assert "1027700123450" in result.text


def test_contains_bik():
    result = extract_docx(FIXTURE)
    assert "044525225" in result.text


def test_extractor_type():
    from app.core.enums import ExtractorType
    result = extract_docx(FIXTURE)
    assert result.extractor_used == ExtractorType.PYTHON_DOCX


def test_ocr_not_used():
    result = extract_docx(FIXTURE)
    assert result.ocr_used is False


def test_no_warnings_on_valid_file():
    result = extract_docx(FIXTURE)
    assert result.warnings == []


def test_raises_on_missing_file():
    with pytest.raises(TextExtractionError):
        extract_docx(Path("tests/fixtures/nonexistent.docx"))


def test_empty_docx_has_warning(tmp_path):
    from docx import Document
    empty = tmp_path / "empty.docx"
    Document().save(str(empty))
    result = extract_docx(empty)
    assert result.warnings
    assert "empty" in result.warnings[0].lower()


def test_extracts_table_content():
    from docx import Document
    fixture = Path("tests/fixtures/sample_with_table.docx")
    result = extract_docx(fixture)
    assert "7744012347" in result.text
    assert "044525225" in result.text


def test_extracts_header_footer():
    fixture = Path("tests/fixtures/sample_with_table.docx")
    result = extract_docx(fixture)
    assert "Реквизиты организации" in result.text
    assert "Конфиденциально" in result.text
