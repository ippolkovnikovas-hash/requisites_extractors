"""
Тесты интерфейса OCR-бэкендов и их фабрики.

До этого бэкенды существовали, но переключаться между ними было нельзя: оба
экстрактора жёстко импортировали TesseractBackend, а `settings.ocr_backend`
использовался ровно в одном месте — в выводе `run_cli.py info`.

Реальный Tesseract здесь не запускается: проверяется контракт и выбор бэкенда,
распознавание подменяется.
"""

import pytest
from PIL import Image

from app.core.exceptions import ConfigError
from app.ocr.base import OcrBackend
from app.ocr.factory import get_ocr_backend


@pytest.fixture
def image():
    return Image.new("L", (10, 10), color=255)


# ── Контракт интерфейса ──────────────────────────────────────────────────────


def test_backend_interface_requires_image_to_text():
    assert hasattr(OcrBackend, "image_to_text")


def test_backend_interface_declares_image_to_lines():
    """image_to_lines используется экстракторами, значит он часть контракта —
    иначе переключение на другой бэкенд падало бы в рантайме."""
    assert hasattr(OcrBackend, "image_to_lines")


def test_default_image_to_lines_splits_text_output(image):
    """Бэкенду достаточно реализовать image_to_text: разбиение по строкам
    есть в базовом классе."""

    class Minimal(OcrBackend):
        def image_to_text(self, image, lang="rus+eng"):
            return "ИНН 7744012347\n\nКПП 774401001\n"

    lines = Minimal().image_to_lines(image)
    assert lines == ["ИНН 7744012347", "КПП 774401001"]


@pytest.mark.parametrize("backend_name", ["tesseract", "easyocr"])
def test_real_backend_names_are_valid_extractor_types(backend_name, monkeypatch):
    """
    `name()` попадает в `TextExtractionResult.extractor_used`, а это строгий
    enum. Если имя бэкенда из него выпадет, экстрактор упадёт на валидации уже
    после распознавания — то есть впустую потратив самую долгую часть работы.
    """
    from app.core.enums import ExtractorType

    assert backend_name in {e.value for e in ExtractorType}


def test_name_defaults_to_class_name():
    class Minimal(OcrBackend):
        def image_to_text(self, image, lang="rus+eng"):
            return ""

    assert Minimal().name() == "Minimal"


# ── Фабрика ──────────────────────────────────────────────────────────────────


def test_factory_returns_tesseract_by_default():
    from app.ocr.tesseract_backend import TesseractBackend

    assert isinstance(get_ocr_backend("tesseract"), TesseractBackend)


def test_factory_follows_settings_when_name_omitted(monkeypatch):
    from app.config import settings
    from app.ocr.tesseract_backend import TesseractBackend

    monkeypatch.setattr(settings, "ocr_backend", "tesseract")
    assert isinstance(get_ocr_backend(), TesseractBackend)


def test_factory_is_case_insensitive():
    from app.ocr.tesseract_backend import TesseractBackend

    assert isinstance(get_ocr_backend("TesseracT"), TesseractBackend)


def test_factory_rejects_unknown_backend():
    with pytest.raises(ConfigError) as exc_info:
        get_ocr_backend("magic_ocr")

    message = str(exc_info.value)
    assert "magic_ocr" in message
    assert "tesseract" in message


def test_factory_builds_easyocr_when_requested(monkeypatch):
    """easyocr — опциональная зависимость, поэтому конструктор подменяем."""
    import app.ocr.easyocr_backend as module

    created = {}

    class FakeEasyOcr(module.EasyOcrBackend):
        def __init__(self):
            created["yes"] = True

    monkeypatch.setattr(module, "EasyOcrBackend", FakeEasyOcr)
    backend = get_ocr_backend("easyocr")

    assert created.get("yes") is True
    assert isinstance(backend, module.EasyOcrBackend)


def test_factory_reports_missing_easyocr_dependency_clearly(monkeypatch):
    """Без установленного easyocr должна быть подсказка, а не голый ImportError."""
    import app.ocr.easyocr_backend as module

    def raise_missing(*args, **kwargs):
        raise ImportError("No module named 'easyocr'")

    monkeypatch.setattr(module, "EasyOcrBackend", raise_missing)

    with pytest.raises(ImportError) as exc_info:
        get_ocr_backend("easyocr")

    assert "easyocr" in str(exc_info.value)


# ── EasyOcrBackend без установленной зависимости ─────────────────────────────


def test_easyocr_module_imports_without_the_package():
    """Модуль обязан импортироваться и без easyocr — иначе упадёт даже фабрика."""
    from app.ocr.easyocr_backend import EasyOcrBackend

    assert EasyOcrBackend.__name__ == "EasyOcrBackend"


def test_easyocr_backend_is_an_ocr_backend():
    from app.ocr.easyocr_backend import EasyOcrBackend

    assert issubclass(EasyOcrBackend, OcrBackend)


def test_easyocr_instantiation_without_package_gives_install_hint(monkeypatch):
    import builtins

    from app.ocr.easyocr_backend import EasyOcrBackend

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "easyocr":
            raise ImportError("No module named 'easyocr'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError) as exc_info:
        EasyOcrBackend()

    assert "requirements/easyocr.txt" in str(exc_info.value)


# ── TesseractBackend: структурный разбор строк ───────────────────────────────


@pytest.fixture
def tesseract(monkeypatch):
    """Бэкенд с подменённым pytesseract — сам Tesseract не запускается."""
    import app.ocr.tesseract_backend as module

    calls = {}

    def fake_image_to_string(image, lang=None, config=None):
        calls["to_string"] = {"lang": lang, "config": config}
        return "  ИНН 7744012347  \n"

    def fake_image_to_data(image, lang=None, config=None, output_type=None):
        calls["to_data"] = {"lang": lang, "config": config}
        # Раскладка настоящего Tesseract: ИНН и КПП лежат в одном блоке, но в
        # разных параграфах, и line_num у обоих равен 1 — он нумеруется внутри
        # параграфа, а не внутри блока.
        return {
            "text": ["ИНН", "7744012347", "", "КПП", "774401001", "   "],
            "page_num": [1, 1, 1, 1, 1, 1],
            "block_num": [1, 1, 1, 1, 1, 2],
            "par_num": [1, 1, 1, 2, 2, 1],
            "line_num": [1, 1, 1, 1, 1, 1],
        }

    monkeypatch.setattr(module.pytesseract, "image_to_string", fake_image_to_string)
    monkeypatch.setattr(module.pytesseract, "image_to_data", fake_image_to_data)
    return module.TesseractBackend(), calls


def test_tesseract_image_to_text_strips_result(tesseract, image):
    backend, _ = tesseract
    assert backend.image_to_text(image) == "ИНН 7744012347"


def test_tesseract_passes_language_through(tesseract, image):
    backend, calls = tesseract
    backend.image_to_text(image, lang="rus")
    assert calls["to_string"]["lang"] == "rus"


def test_tesseract_groups_words_into_lines(tesseract, image):
    """Слова собираются в строки по полному адресу строки — это и есть
    структурный OCR вместо плоского image_to_string."""
    backend, _ = tesseract
    assert backend.image_to_lines(image) == ["ИНН 7744012347", "КПП 774401001"]


def test_tesseract_does_not_merge_lines_from_different_paragraphs(tesseract, image):
    """
    Регрессия: `line_num` уникален внутри параграфа, а не внутри блока. Пока в
    ключе группировки не было `par_num`, строки разных параграфов с одинаковым
    номером сливались в одну. На реальной карточке контрагента документ
    схлопывался в две строки вместо пятнадцати, после чего построчный
    regex-слой начинал затаскивать в поле содержимое соседних строк.
    """
    backend, _ = tesseract
    lines = backend.image_to_lines(image)

    assert len(lines) == 2
    assert lines[0] == "ИНН 7744012347"
    assert lines[1] == "КПП 774401001"


def test_tesseract_skips_empty_recognised_words(tesseract, image):
    backend, _ = tesseract
    lines = backend.image_to_lines(image)
    assert all(line.strip() for line in lines)
    assert not any("  " in line for line in lines)


def test_tesseract_name_is_stable(tesseract):
    backend, _ = tesseract
    assert backend.name() == "tesseract"


def test_tesseract_cmd_applied_when_configured(monkeypatch):
    import app.ocr.tesseract_backend as module

    monkeypatch.setattr(module.pytesseract.pytesseract, "tesseract_cmd", "unset")
    module.TesseractBackend(tesseract_cmd="C:/tools/tesseract.exe")
    assert module.pytesseract.pytesseract.tesseract_cmd == "C:/tools/tesseract.exe"


def test_tesseract_cmd_left_alone_when_not_configured(monkeypatch):
    import app.ocr.tesseract_backend as module

    monkeypatch.setattr(module.pytesseract.pytesseract, "tesseract_cmd", "keep-me")
    module.TesseractBackend(tesseract_cmd=None)
    assert module.pytesseract.pytesseract.tesseract_cmd == "keep-me"


# ── EasyOcrBackend: распознавание через подменённый reader ───────────────────


def test_easyocr_joins_reader_output(monkeypatch, image):
    # numpy приходит вместе с easyocr — без опциональной зависимости этот путь
    # физически не выполняется, и проверять его нечем.
    pytest.importorskip("numpy", reason="ставится вместе с easyocr")

    from app.ocr.easyocr_backend import EasyOcrBackend

    backend = EasyOcrBackend.__new__(EasyOcrBackend)

    class FakeReader:
        def readtext(self, array, detail=0, paragraph=True):
            return ["ИНН 7744012347", "КПП 774401001"]

    backend._reader = FakeReader()

    assert backend.image_to_text(image) == "ИНН 7744012347\nКПП 774401001"


def test_easyocr_name_is_stable():
    from app.ocr.easyocr_backend import EasyOcrBackend

    backend = EasyOcrBackend.__new__(EasyOcrBackend)
    assert backend.name() == "easyocr"


def test_easyocr_inherits_default_line_splitting(monkeypatch, image):
    pytest.importorskip("numpy", reason="ставится вместе с easyocr")

    from app.ocr.easyocr_backend import EasyOcrBackend

    backend = EasyOcrBackend.__new__(EasyOcrBackend)

    class FakeReader:
        def readtext(self, array, detail=0, paragraph=True):
            return ["ИНН 7744012347", "", "КПП 774401001"]

    backend._reader = FakeReader()

    assert backend.image_to_lines(image) == ["ИНН 7744012347", "КПП 774401001"]


# ── Экстракторы берут бэкенд из фабрики ──────────────────────────────────────


def test_image_extractor_uses_factory(monkeypatch, tmp_path):
    """Экстрактор не должен жёстко импортировать Tesseract."""
    import app.extractors.image_ocr_extractor as extractor

    calls = []

    class FakeBackend(OcrBackend):
        def image_to_text(self, image, lang="rus+eng"):
            return "ИНН 7744012347"

        def image_to_lines(self, image, lang="rus+eng"):
            calls.append("lines")
            return ["ИНН 7744012347"]

        def name(self):
            return "tesseract"

    monkeypatch.setattr(extractor, "get_ocr_backend", lambda: FakeBackend())

    path = tmp_path / "scan.png"
    Image.new("L", (20, 20), color=255).save(path)

    result = extractor.extract_image_ocr(path)

    assert calls == ["lines"]
    assert "7744012347" in result.text
    assert result.ocr_used is True


def test_pdf_ocr_extractor_uses_factory(monkeypatch, tmp_path):
    import app.extractors.pdf_ocr_extractor as extractor

    class FakeBackend(OcrBackend):
        def image_to_text(self, image, lang="rus+eng"):
            return "ИНН 7744012347"

        def image_to_lines(self, image, lang="rus+eng"):
            return ["ИНН 7744012347"]

        def name(self):
            return "tesseract"

    monkeypatch.setattr(extractor, "get_ocr_backend", lambda: FakeBackend())
    monkeypatch.setattr(
        extractor, "convert_from_path", lambda *a, **kw: [Image.new("L", (20, 20), 255)]
    )

    result = extractor.extract_pdf_ocr(tmp_path / "scan.pdf")

    assert "7744012347" in result.text
    assert result.pages == 1
    assert result.ocr_used is True
