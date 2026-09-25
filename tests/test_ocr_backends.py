"""Тесты выбора OCR-бэкенда и дополнительных проходов OCR."""
from PIL import Image

import app.extractors.image_ocr_extractor as io
from app.config import settings
from app.ocr import get_ocr_backend
from app.ocr.base import OcrBackend
from app.ocr.tesseract_backend import TesseractBackend


class _PsmBackend(OcrBackend):
    supports_psm = True

    def __init__(self):
        self.psms = []

    def name(self):
        return "tesseract"

    def image_to_text(self, image, lang="rus+eng"):
        return ""

    def image_to_lines(self, image, lang="rus+eng", psm=6):
        self.psms.append(psm)
        return [f"psm{psm}"]


class _PlainBackend(OcrBackend):
    def image_to_text(self, image, lang="rus+eng"):
        return "строка 1\n\nстрока 2"


def test_factory_defaults_to_tesseract(monkeypatch):
    monkeypatch.setattr(settings, "ocr_backend", "tesseract")
    assert isinstance(get_ocr_backend(), TesseractBackend)


def test_factory_unknown_falls_back_to_tesseract(monkeypatch):
    monkeypatch.setattr(settings, "ocr_backend", "nonexistent")
    assert isinstance(get_ocr_backend(), TesseractBackend)


def test_base_image_to_lines_splits_text():
    assert _PlainBackend().image_to_lines(Image.new("L", (10, 10))) == ["строка 1", "строка 2"]


def test_extra_passes_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ocr_extra_passes", True)
    backend = _PsmBackend()
    main, alts = io.ocr_passes(backend, Image.new("L", (10, 10)))
    assert main == "psm6"
    assert alts == ["psm4", "psm11"]


def test_extra_passes_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ocr_extra_passes", False)
    main, alts = io.ocr_passes(_PsmBackend(), Image.new("L", (10, 10)))
    assert alts == []


def test_extra_passes_skipped_for_backend_without_psm(monkeypatch):
    monkeypatch.setattr(settings, "ocr_extra_passes", True)
    main, alts = io.ocr_passes(_PlainBackend(), Image.new("L", (10, 10)))
    assert main == "строка 1\nстрока 2"
    assert alts == []


def test_image_extractor_uses_exif_and_returns_alts(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ocr_extra_passes", True)
    backend = _PsmBackend()
    monkeypatch.setattr(io, "get_ocr_backend", lambda: backend)
    path = tmp_path / "photo.png"
    Image.new("RGB", (100, 50), "white").save(path)
    result = io.extract_image_ocr(path)
    assert result.ocr_used
    assert result.text == "psm6"
    assert result.alt_texts == ["psm4", "psm11"]
