"""Тесты OCR PDF: запасной рендер через pypdfium2, когда Poppler недоступен."""
from pathlib import Path

import app.extractors.pdf_ocr_extractor as po

PDF_FIXTURE = Path(__file__).parent / "fixtures" / "sample_two_pages.pdf"


class _FakeBackend:
    supports_psm = False

    def __init__(self, *args, **kwargs):
        pass

    def name(self):
        return "tesseract"

    def image_to_lines(self, image, psm=6):
        return [f"ИНН 7707083893 size={image.size[0]}"]


def test_falls_back_to_pdfium_when_poppler_missing(monkeypatch):
    def no_poppler(*args, **kwargs):
        raise RuntimeError("Unable to get page count. Is poppler installed and in PATH?")

    monkeypatch.setattr(po, "convert_from_path", no_poppler)
    monkeypatch.setattr(po, "get_ocr_backend", _FakeBackend)

    result = po.extract_pdf_ocr(PDF_FIXTURE)

    assert result.pages == 2
    assert result.ocr_used
    assert "ИНН 7707083893" in result.text
    assert any("pypdfium2" in w for w in result.warnings)
