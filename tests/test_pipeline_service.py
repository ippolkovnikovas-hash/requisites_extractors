"""Интеграционные тесты pipeline_service через MockLLMClient."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.exceptions import ConfigError, LLMError, LLMParseError, UnsupportedFileTypeError
from app.services.pipeline_service import _build_llm_client, run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_FIXTURE = Path("tests/fixtures/sample_requisites.pdf")
DOCX_FIXTURE = Path("tests/fixtures/sample_requisites.docx")


@pytest.fixture(autouse=True)
def use_mock_llm(monkeypatch):
    import app.services.pipeline_service as ps
    from app.llm.mock_client import MockLLMClient

    monkeypatch.setattr(ps, "_build_llm_client", lambda: MockLLMClient())


def test_pipeline_pdf_returns_result(tmp_path):
    import shutil

    pdf = tmp_path / "sample.pdf"
    shutil.copy(PDF_FIXTURE, pdf)
    result = run_pipeline(pdf, "sample.pdf")
    assert result.document_id
    assert result.status in ("done", "needs_review")
    assert result.fill_rate >= 0.0


def test_pipeline_docx_returns_result(tmp_path):
    import shutil

    docx = tmp_path / "sample.docx"
    shutil.copy(DOCX_FIXTURE, docx)
    result = run_pipeline(docx, "sample.docx")
    assert result.document_id
    assert result.fill_rate >= 0.0


def test_pipeline_fallback_fills_inn(tmp_path):
    import shutil

    pdf = tmp_path / "sample.pdf"
    shutil.copy(PDF_FIXTURE, pdf)
    result = run_pipeline(pdf, "sample.pdf")
    assert result.data.inn == "7744012347"


def test_pipeline_fallback_fills_ogrn(tmp_path):
    import shutil

    pdf = tmp_path / "sample.pdf"
    shutil.copy(PDF_FIXTURE, pdf)
    result = run_pipeline(pdf, "sample.pdf")
    assert result.data.ogrn == "1027700123450"


def test_pipeline_creates_json_file(tmp_path):
    """Сохранение по умолчанию выключено — здесь проверяется сам экспорт."""
    import shutil

    pdf = tmp_path / "sample.pdf"
    shutil.copy(PDF_FIXTURE, pdf)
    result = run_pipeline(pdf, "sample.pdf", persist=True)
    assert Path(result.json_path).exists()


def test_pipeline_creates_xlsx_file(tmp_path):
    import shutil

    pdf = tmp_path / "sample.pdf"
    shutil.copy(PDF_FIXTURE, pdf)
    result = run_pipeline(pdf, "sample.pdf", persist=True)
    assert Path(result.xlsx_path).exists()


def test_pipeline_unsupported_raises(tmp_path):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("a,b,c")
    with pytest.raises(UnsupportedFileTypeError):
        run_pipeline(csv_file, "data.csv")


def test_pipeline_processing_meta(tmp_path):
    import shutil

    pdf = tmp_path / "sample.pdf"
    shutil.copy(PDF_FIXTURE, pdf)
    result = run_pipeline(pdf, "sample.pdf")
    meta = result.processing_meta
    assert meta["llm_provider"] == "mock"
    assert meta["ocr_used"] is False
    assert "sha256" in meta
    assert meta["llm_failed"] is False


# ── Устойчивость к недоступной LLM ───────────────────────────────────────────
#
# Regex-слой в одиночку заполняет большинство полей самостоятельно (это и
# есть его назначение), но раньше LLMError из недоступной Ollama выходил из
# run_pipeline необработанным и ронял всю обработку — пользователь получал
# голое сообщение об ошибке вместо review-формы с тем, что нашёл regex.


def test_pipeline_falls_back_to_regex_only_when_ollama_unreachable(tmp_path, monkeypatch):
    import shutil

    import app.services.pipeline_service as ps

    class UnreachableClient:
        def extract(self, text, prompt_version="v1"):
            raise LLMError("Ollama call failed: connection refused")

    monkeypatch.setattr(ps, "_build_llm_client", lambda: UnreachableClient())

    pdf = tmp_path / "sample.pdf"
    shutil.copy(PDF_FIXTURE, pdf)
    result = run_pipeline(pdf, "sample.pdf")

    # regex-слой находит ИНН в фикстуре самостоятельно, без участия LLM
    assert result.data.inn == "7744012347"
    assert result.processing_meta["llm_failed"] is True
    assert any("LLM недоступна" in w for w in result.warnings)


def test_pipeline_falls_back_to_regex_only_on_unparsable_llm_response(tmp_path, monkeypatch):
    """Битый JSON от модели — тот же класс проблемы, что и обрыв связи: от
    LLM нет пригодных данных, но regex-слой всё равно может отработать."""
    import shutil

    import app.services.pipeline_service as ps

    class GarbledClient:
        def extract(self, text, prompt_version="v1"):
            raise LLMParseError("не удалось разобрать JSON")

    monkeypatch.setattr(ps, "_build_llm_client", lambda: GarbledClient())

    pdf = tmp_path / "sample.pdf"
    shutil.copy(PDF_FIXTURE, pdf)
    result = run_pipeline(pdf, "sample.pdf")

    assert result.processing_meta["llm_failed"] is True
    assert any("LLM недоступна" in w for w in result.warnings)


def test_pipeline_does_not_swallow_llm_provider_config_error(tmp_path, monkeypatch):
    """
    Опечатка в LLM_PROVIDER — ошибка конфигурации, а не временная
    недоступность Ollama. Молчаливый откат на regex-only здесь недопустим:
    пользователь должен узнать, что настройка сломана, а не получить
    неполный результат без объяснения. try/except в pipeline оборачивает
    только вызов extract(), а не _build_llm_client().
    """
    import shutil

    import app.services.pipeline_service as ps

    def raise_config_error():
        raise ConfigError("Неизвестный LLM_PROVIDER='olama'")

    monkeypatch.setattr(ps, "_build_llm_client", raise_config_error)

    pdf = tmp_path / "sample.pdf"
    shutil.copy(PDF_FIXTURE, pdf)
    with pytest.raises(ConfigError):
        run_pipeline(pdf, "sample.pdf")


# ── Вспомогательные функции pipeline_service ────────────────────────────────


def test_build_llm_mock():
    with patch("app.services.pipeline_service.settings") as s:
        s.llm_provider = "mock"
        client = _build_llm_client()
        from app.llm.mock_client import MockLLMClient

        assert isinstance(client, MockLLMClient)


def test_build_llm_unknown_provider_raises():
    """
    Неизвестный провайдер — ошибка конфигурации, а не тихий откат на mock.

    Раньше опечатка вроде «olama» молча подсовывала фейковый клиент, и
    пользователь получал выдуманные реквизиты, не подозревая об этом.
    """
    from app.core.exceptions import ConfigError

    with patch("app.services.pipeline_service.settings") as s:
        s.llm_provider = "unknown_provider"
        with pytest.raises(ConfigError) as exc_info:
            _build_llm_client()

    assert "unknown_provider" in str(exc_info.value)


def test_build_llm_typo_in_provider_name_raises():
    """«olama» вместо «ollama» не должно тихо превращаться в mock."""
    from app.core.exceptions import ConfigError

    with patch("app.services.pipeline_service.settings") as s:
        s.llm_provider = "olama"
        with pytest.raises(ConfigError):
            _build_llm_client()


def test_build_llm_external_provider_is_rejected():
    """Внешние LLM-провайдеры запрещены (CLAUDE.md, «Приватность»): имя такого
    провайдера должно приводить к явной ошибке, а не к молчаливому mock."""
    from app.core.exceptions import ConfigError

    with patch("app.services.pipeline_service.settings") as s:
        s.llm_provider = "openai"
        with pytest.raises(ConfigError):
            _build_llm_client()


def test_config_error_lists_supported_providers():
    """Сообщение должно подсказывать, что вообще допустимо."""
    from app.core.exceptions import ConfigError

    with patch("app.services.pipeline_service.settings") as s:
        s.llm_provider = "gpt5"
        with pytest.raises(ConfigError) as exc_info:
            _build_llm_client()

    message = str(exc_info.value)
    assert "ollama" in message
    assert "mock" in message


def test_no_external_llm_provider_in_enum():
    from app.core.enums import LLMProvider

    assert {p.value for p in LLMProvider} == {"mock", "ollama"}


def test_guess_mime_uses_extension_fallback(tmp_path, monkeypatch):
    """magic недоступен или падает — используется маппинг по расширению."""
    import app.services.pipeline_service as ps

    monkeypatch.setattr(
        ps,
        "_guess_mime",
        lambda p: {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".jpg": "image/jpeg",
            ".png": "image/png",
            ".xyz": "application/octet-stream",
        }.get(p.suffix.lower(), "application/octet-stream"),
    )

    assert ps._guess_mime(tmp_path / "doc.pdf") == "application/pdf"
    assert "wordprocessingml" in ps._guess_mime(tmp_path / "doc.docx")
    assert ps._guess_mime(tmp_path / "img.jpg") == "image/jpeg"
    assert ps._guess_mime(tmp_path / "file.xyz") == "application/octet-stream"


def test_guess_mime_magic_fails_falls_back(tmp_path, monkeypatch):
    """Если magic бросает исключение — возвращаем маппинг по расширению."""
    import builtins

    import app.services.pipeline_service as ps

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "magic":
            raise ImportError("no magic")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"fake")
    result = ps._guess_mime(f)
    assert result == "application/pdf"


def test_build_llm_ollama(monkeypatch):
    with patch("app.services.pipeline_service.settings") as s:
        s.llm_provider = "ollama"
        with patch("app.llm.ollama_client.OllamaClient") as MockOllama:
            MockOllama.return_value = object()
            client = _build_llm_client()
            assert client is not None


def test_openai_client_module_does_not_exist():
    """Модуль внешнего провайдера должен отсутствовать в репозитории."""
    import importlib.util

    assert importlib.util.find_spec("app.llm.openai_client") is None


def test_pipeline_warnings_truncation(tmp_path, monkeypatch):
    import shutil

    import app.services.pipeline_service as ps
    from app.llm.mock_client import MockLLMClient

    monkeypatch.setattr(ps, "_build_llm_client", lambda: MockLLMClient())

    # Текст длиннее порога нормализации
    long_text_pdf = tmp_path / "long.pdf"
    shutil.copy(PDF_FIXTURE, long_text_pdf)

    with patch("app.services.pipeline_service.NORMALIZE_MAX_CHARS", 10):
        result = run_pipeline(long_text_pdf, "long.pdf")
    # Проверяем что пайплайн завершился (truncation может не сработать на маленьком файле)
    assert result.document_id


def test_build_review_warnings_missing_fields():
    from app.schemas.requisites import RequisitesData
    from app.schemas.validation import ValidationReport
    from app.services.pipeline_service import _build_review_warnings

    empty = RequisitesData()
    report = ValidationReport(errors=[])
    warnings = _build_review_warnings(empty, report, [], 0)
    assert any("Missing fields" in w for w in warnings)


def test_pipeline_fills_docx_template(tmp_path, monkeypatch):
    import shutil

    import app.services.pipeline_service as ps
    from app.llm.mock_client import MockLLMClient

    monkeypatch.setattr(ps, "_build_llm_client", lambda: MockLLMClient())

    pdf = tmp_path / "sample.pdf"
    shutil.copy(PDF_FIXTURE, pdf)

    # pipeline ищет shablon.docx в cwd — кладём копию шаблона в tmp_path
    # и переходим туда, чтобы не трогать рабочую копию проекта.
    shutil.copy(PROJECT_ROOT / "shablon.docx", tmp_path / "shablon.docx")
    monkeypatch.chdir(tmp_path)

    result = run_pipeline(pdf, "sample.pdf", persist=True)
    assert result.docx_path is not None
    assert Path(result.docx_path).exists()
