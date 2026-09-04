"""
Тесты LLM-слоя: версии промптов, mock-клиент и клиент Ollama.

Сеть не используется: `httpx.post` подменяется. Это принципиально — тесты не
должны зависеть от того, поднята ли Ollama на машине разработчика, и тем более
не должны никуда ходить с текстом документа.
"""

import json

import pytest

from app.core.exceptions import LLMError, LLMParseError
from app.llm.mock_client import MockLLMClient
from app.llm.prompts import DEFAULT_VERSION, get_prompt, list_versions

# ── Промпты ──────────────────────────────────────────────────────────────────


def test_list_versions_includes_text_and_image_profiles():
    versions = list_versions()
    assert "v1" in versions
    assert "image" in versions


def test_default_version_is_available():
    assert DEFAULT_VERSION in list_versions()


@pytest.mark.parametrize("version", ["v1", "v2", "v3", "image"])
def test_get_prompt_substitutes_document_text(version):
    prompt = get_prompt(version, "ИНН 7744012347")
    assert "ИНН 7744012347" in prompt
    assert "{document_text}" not in prompt


def test_get_prompt_rejects_unknown_version():
    with pytest.raises(ValueError) as exc_info:
        get_prompt("v99", "текст")

    message = str(exc_info.value)
    assert "v99" in message
    assert "v1" in message


@pytest.mark.parametrize("version", ["v1", "v3", "image"])
def test_get_prompt_unescapes_json_example_braces(version):
    """
    Шаблоны написаны под `.format()` и хранят экранированные `{{` / `}}`, а
    подстановка делается через `.replace()`. Пока экранирование не снималось,
    модель получала пример ответа с двойными скобками — то есть синтаксически
    битый JSON в роли образца.
    """
    prompt = get_prompt(version, "ИНН 7744012347")

    assert "{{" not in prompt
    assert "}}" not in prompt
    assert '{\n  "company_name"' in prompt


def test_image_prompt_mentions_ocr_specific_problems():
    """Профиль для OCR должен отличаться по существу, а не только именем."""
    prompt = get_prompt("image", "текст")
    lowered = prompt.lower()
    assert "ocr" in lowered
    assert "пробел" in lowered


# ── Mock-клиент ──────────────────────────────────────────────────────────────


def test_mock_client_returns_all_sixteen_fields():
    from app.schemas.requisites import RequisitesData

    result = MockLLMClient().extract("любой текст")
    assert set(result.parsed_data) == set(RequisitesData.model_fields)


def test_mock_client_reports_itself_as_mock():
    result = MockLLMClient().extract("текст")
    assert result.provider == "mock"
    assert result.model_name == "mock"


def test_mock_client_echoes_prompt_version():
    result = MockLLMClient().extract("текст", prompt_version="image")
    assert result.prompt_version == "image"


def test_mock_client_raw_response_is_valid_json():
    result = MockLLMClient().extract("текст")
    assert json.loads(result.raw_response) == result.parsed_data


# ── Клиент Ollama ────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, payload, status_ok=True):
        self._payload = payload
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("HTTP 500")

    def json(self):
        return self._payload


@pytest.fixture
def ollama(monkeypatch):
    import app.llm.ollama_client as module

    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse({"response": captured.get("reply", "{}")})

    monkeypatch.setattr(module.httpx, "post", fake_post)
    return module, captured


def test_ollama_calls_local_generate_endpoint(ollama):
    module, captured = ollama
    captured["reply"] = '{"inn": "7744012347"}'

    module.OllamaClient().extract("ИНН 7744012347")

    assert captured["url"].endswith("/api/generate")
    assert captured["url"].startswith("http://localhost")


def test_ollama_requests_structured_json_schema_without_streaming(ollama):
    """
    Регрессия: `format: "json"` только принуждает Ollama выдать синтаксически
    валидный JSON — имена и состав полей модель по-прежнему может придумать
    сама. Схема `RequisitesData` задаёт их точно, и дрейф имён полей исчезает.
    """
    module, captured = ollama
    captured["reply"] = "{}"

    module.OllamaClient().extract("текст")

    assert captured["json"]["stream"] is False
    fmt = captured["json"]["format"]
    assert fmt["type"] == "object"
    assert set(fmt["properties"]) == {
        "company_name",
        "short_name",
        "legal_address",
        "postal_address",
        "ogrn",
        "inn",
        "kpp",
        "bank_name",
        "checking_account",
        "correspondent_account",
        "bik",
        "ceo_position",
        "ceo_fio_full",
        "ceo_fio",
        "phone",
        "email",
    }


def test_ollama_uses_deterministic_temperature_and_explicit_context(ollama):
    """
    Регрессия: запрос уходил без `options` вовсе — на дефолтной temperature
    0.8 экстракция реквизитов недетерминирована, а без явного `num_ctx`
    версия Ollama с меньшим дефолтом контекста молча обрезала бы начало
    промпта, то есть все инструкции.
    """
    from app.config import settings

    module, captured = ollama
    captured["reply"] = "{}"

    module.OllamaClient().extract("текст")

    assert captured["json"]["options"]["temperature"] == settings.ollama_temperature
    assert captured["json"]["options"]["num_ctx"] == settings.ollama_num_ctx


def test_ollama_temperature_and_context_are_configurable(ollama, monkeypatch):
    module, captured = ollama
    captured["reply"] = "{}"

    monkeypatch.setattr(module.settings, "ollama_temperature", 0.3)
    monkeypatch.setattr(module.settings, "ollama_num_ctx", 16384)

    module.OllamaClient().extract("текст")

    assert captured["json"]["options"]["temperature"] == 0.3
    assert captured["json"]["options"]["num_ctx"] == 16384


def test_ollama_sends_rendered_prompt_not_raw_text(ollama):
    module, captured = ollama
    captured["reply"] = "{}"

    module.OllamaClient().extract("ИНН 7744012347", prompt_version="v1")

    prompt = captured["json"]["prompt"]
    assert "ИНН 7744012347" in prompt
    assert len(prompt) > len("ИНН 7744012347")


def test_ollama_parses_response_into_result(ollama):
    module, captured = ollama
    captured["reply"] = '{"inn": "7744012347", "kpp": "774401001"}'

    result = module.OllamaClient().extract("текст")

    assert result.parsed_data["inn"] == "7744012347"
    assert result.provider == "ollama"


def test_ollama_reports_prompt_version_used(ollama):
    module, captured = ollama
    captured["reply"] = "{}"

    result = module.OllamaClient().extract("текст", prompt_version="image")

    assert result.prompt_version == "image"


def test_ollama_wraps_transport_failure(monkeypatch):
    import app.llm.ollama_client as module

    def boom(*args, **kwargs):
        raise ConnectionError("Ollama не запущена")

    monkeypatch.setattr(module.httpx, "post", boom)

    with pytest.raises(LLMError) as exc_info:
        module.OllamaClient().extract("текст")

    assert "Ollama" in str(exc_info.value)


def test_ollama_reports_unparsable_json_separately(ollama):
    """Битый ответ модели — это не сбой связи, и путать их нельзя."""
    module, captured = ollama
    captured["reply"] = "конечно, вот реквизиты: ИНН ..."

    with pytest.raises(LLMParseError):
        module.OllamaClient().extract("текст")


# ── Выбор профиля промпта в pipeline ─────────────────────────────────────────


def _run_pipeline_capturing_prompt_version(monkeypatch, ocr_used):
    """Прогоняет pipeline с подменёнными экстрактором и LLM, возвращает версию
    промпта, с которой был вызван клиент."""
    import app.services.pipeline_service as ps
    from app.schemas.extraction import LLMExtractionResult, TextExtractionResult

    used = {}

    class CapturingClient:
        def extract(self, text, prompt_version="v1"):
            used["version"] = prompt_version
            return LLMExtractionResult(
                raw_response="{}",
                parsed_data={},
                model_name="mock",
                provider="mock",
                prompt_version=prompt_version,
            )

    monkeypatch.setattr(ps, "_build_llm_client", lambda: CapturingClient())
    monkeypatch.setattr(
        ps,
        "extract_text",
        lambda doc: TextExtractionResult(
            text="ИНН 7744012347",
            extractor_used="tesseract" if ocr_used else "pdfplumber",
            ocr_used=ocr_used,
            pages=1,
        ),
    )
    return used


def test_ocr_document_uses_image_prompt_profile(tmp_path, monkeypatch):
    """
    Профиль `image` написан под распознанный текст, но раньше не выбирался
    никогда: pipeline всегда брал settings.prompt_version.
    """
    import shutil

    from app.services.pipeline_service import run_pipeline

    used = _run_pipeline_capturing_prompt_version(monkeypatch, ocr_used=True)
    pdf = tmp_path / "scan.pdf"
    shutil.copy("tests/fixtures/sample_requisites.pdf", pdf)

    run_pipeline(pdf, "scan.pdf")

    assert used["version"] == "image"


def test_text_document_uses_configured_prompt(tmp_path, monkeypatch):
    import shutil

    from app.config import settings
    from app.services.pipeline_service import run_pipeline

    monkeypatch.setattr(settings, "prompt_version", "v2")
    used = _run_pipeline_capturing_prompt_version(monkeypatch, ocr_used=False)
    pdf = tmp_path / "doc.pdf"
    shutil.copy("tests/fixtures/sample_requisites.pdf", pdf)

    run_pipeline(pdf, "doc.pdf")

    assert used["version"] == "v2"


def test_ocr_prompt_profile_is_configurable(tmp_path, monkeypatch):
    import shutil

    from app.config import settings
    from app.services.pipeline_service import run_pipeline

    monkeypatch.setattr(settings, "ocr_prompt_version", "v3")
    used = _run_pipeline_capturing_prompt_version(monkeypatch, ocr_used=True)
    pdf = tmp_path / "scan.pdf"
    shutil.copy("tests/fixtures/sample_requisites.pdf", pdf)

    run_pipeline(pdf, "scan.pdf")

    assert used["version"] == "v3"
