"""Тесты PDF text-экстрактора."""

from pathlib import Path

import pytest

from app.core.enums import ExtractorType
from app.core.exceptions import TextExtractionError
from app.extractors.pdf_text_extractor import extract_pdf_text

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
    """
    Если поиск таблиц на странице упал — обычный текст всё равно должен
    извлечься, а не пропасть вместе с ошибкой.
    """
    import pdfplumber

    class FakePage:
        def extract_text(self, **kw):
            return "ИНН: 7744012347"

        def find_tables(self):
            raise RuntimeError("table parse error")

    class FakePDF:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(pdfplumber, "open", lambda *a, **kw: FakePDF())
    result = extract_pdf_text(tmp_path / "fake.pdf")
    assert any("table extraction failed" in w for w in result.warnings)
    assert "7744012347" in result.text


def test_table_cell_text_is_not_duplicated_in_prose(tmp_path):
    """
    Регрессия: `page.extract_text()` уже включает содержимое ячеек таблицы в
    общий поток текста в порядке чтения, а `extract_tables()` добавлял то же
    самое ещё раз отдельным блоком. Вход LLM раздувался вдвое, а regex-слой
    находил каждое значение дважды. На реальной карточке с таблицей реквизитов
    это означало, что расчётный счёт попадал в текст и как часть прозы, и как
    часть табличной строки.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    pdf_path = tmp_path / "table.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
    table = Table([["INN", "7744012347"], ["BIK", "044525225"]])
    # Без видимых линий сетки pdfplumber вообще не распознаёт таблицу как
    # таблицу — тогда бага и проверять нечего.
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))
    doc.build([table])

    result = extract_pdf_text(pdf_path)

    assert result.text.count("7744012347") == 1
    assert "INN | 7744012347" in result.text
