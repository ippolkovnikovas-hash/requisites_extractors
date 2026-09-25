"""Тесты Yandex Vision OCR и YandexGPT без сетевых вызовов."""
import json
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from app.config import settings
from app.core.exceptions import LLMError, TextExtractionError


@pytest.fixture
def yandex_settings(monkeypatch):
    monkeypatch.setattr(settings, "yandex_api_key", "test-key")
    monkeypatch.setattr(settings, "yandex_folder_id", "b1gfolder")
    monkeypatch.setattr(settings, "yandex_data_logging", False)


# ── Vision OCR ───────────────────────────────────────────────────────────────

_VISION_RESPONSE = {
    "result": {
        "textAnnotation": {
            "fullText": "ИНН 7707083893\nБИК 044525225",
            "blocks": [
                {"lines": [{"text": "ИНН 7707083893"}, {"text": "БИК 044525225"}]},
            ],
        }
    }
}


def test_vision_sends_headers_and_parses_lines(yandex_settings, monkeypatch):
    from app.ocr import yandex_vision_backend as yv

    captured = {}

    def fake_post(url, json, headers, timeout):
        captured.update(url=url, body=json, headers=headers)
        return httpx.Response(200, json=_VISION_RESPONSE)

    monkeypatch.setattr(yv.httpx, "post", fake_post)
    lines = yv.YandexVisionBackend().image_to_lines(Image.new("RGB", (40, 20), "white"))

    assert lines == ["ИНН 7707083893", "БИК 044525225"]
    assert captured["headers"]["Authorization"] == "Api-Key test-key"
    assert captured["headers"]["x-folder-id"] == "b1gfolder"
    assert captured["headers"]["x-data-logging-enabled"] == "false"
    assert captured["body"]["mimeType"] == "JPEG"
    assert captured["body"]["content"]


def test_vision_falls_back_to_full_text():
    from app.ocr.yandex_vision_backend import _lines_from_response

    payload = {"textAnnotation": {"fullText": "строка 1\n\nстрока 2", "blocks": []}}
    assert _lines_from_response(payload) == ["строка 1", "строка 2"]


def test_vision_downscales_huge_image():
    import base64
    import io

    from app.ocr.yandex_vision_backend import _MAX_PIXELS, _encode_image

    encoded = _encode_image(Image.new("L", (6000, 4000), "white"))
    w, h = Image.open(io.BytesIO(base64.b64decode(encoded))).size
    assert w * h <= _MAX_PIXELS


def test_vision_http_error_raises(yandex_settings, monkeypatch):
    from app.ocr import yandex_vision_backend as yv

    monkeypatch.setattr(yv.httpx, "post", lambda *a, **k: httpx.Response(401, json={"error": "x"}))
    with pytest.raises(TextExtractionError, match="HTTP 401"):
        yv.YandexVisionBackend().image_to_lines(Image.new("RGB", (10, 10)))


def test_vision_requires_credentials(monkeypatch):
    from app.ocr.yandex_vision_backend import YandexVisionBackend

    monkeypatch.setattr(settings, "yandex_api_key", "")
    with pytest.raises(TextExtractionError, match="YANDEX_API_KEY"):
        YandexVisionBackend()


def test_factory_wraps_yandex_with_fallback(yandex_settings, monkeypatch):
    from app.ocr import FallbackOcrBackend, get_ocr_backend

    monkeypatch.setattr(settings, "ocr_backend", "yandex")
    backend = get_ocr_backend()
    assert isinstance(backend, FallbackOcrBackend)
    assert backend.needs_preprocessing is False
    assert backend.name() == "yandex_vision"


def test_factory_yandex_without_keys_uses_tesseract(monkeypatch):
    from app.ocr import get_ocr_backend
    from app.ocr.tesseract_backend import TesseractBackend

    monkeypatch.setattr(settings, "ocr_backend", "yandex")
    monkeypatch.setattr(settings, "yandex_api_key", "")
    assert isinstance(get_ocr_backend(), TesseractBackend)


def test_fallback_backend_uses_tesseract_on_error():
    from app.ocr import FallbackOcrBackend
    from app.ocr.base import OcrBackend

    class Broken(OcrBackend):
        def image_to_text(self, image, lang="rus+eng"):
            raise TextExtractionError("network down")

        def name(self):
            return "yandex_vision"

    class Local(OcrBackend):
        def image_to_text(self, image, lang="rus+eng"):
            return "локально"

        def name(self):
            return "tesseract"

    backend = FallbackOcrBackend(Broken(), fallback_factory=Local)
    assert backend.image_to_lines(Image.new("RGB", (10, 10))) == ["локально"]
    assert backend.fallback_used
    assert backend.name() == "tesseract"


def test_image_extractor_sends_raw_image_to_cloud(tmp_path, monkeypatch):
    import app.extractors.image_ocr_extractor as io_mod
    from app.ocr.base import OcrBackend

    seen = {}

    class Cloud(OcrBackend):
        needs_preprocessing = False

        def image_to_text(self, image, lang="rus+eng"):
            seen["mode"] = image.mode
            seen["size"] = image.size
            return "ok"

        def name(self):
            return "yandex_vision"

    monkeypatch.setattr(io_mod, "get_ocr_backend", Cloud)
    path = tmp_path / "photo.jpg"
    Image.new("RGB", (120, 80), "white").save(path)
    result = io_mod.extract_image_ocr(path)
    assert result.text == "ok"
    assert seen == {"mode": "RGB", "size": (120, 80)}  # без серого и увеличения
    assert result.alt_texts == []


# ── YandexGPT ────────────────────────────────────────────────────────────────

def _fake_completion(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_yandexgpt_parses_structured_answer(yandex_settings, monkeypatch):
    from app.llm.yandex_client import YandexGPTClient

    client = YandexGPTClient()
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return _fake_completion(json.dumps({"company_name": "ООО «Ромашка»", "inn": "", "extra": "x"}))

    monkeypatch.setattr(client._client.chat.completions, "create", create)
    result = client.extract("текст", "v1")

    assert result.provider == "yandex"
    assert result.parsed_data == {"company_name": "ООО «Ромашка»", "inn": None}
    assert calls[0]["model"] == f"gpt://b1gfolder/{settings.yandex_gpt_model}"
    assert calls[0]["response_format"]["type"] == "json_schema"


def test_yandexgpt_retries_without_schema(yandex_settings, monkeypatch):
    from app.llm.yandex_client import YandexGPTClient

    client = YandexGPTClient()
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if "response_format" in kwargs:
            raise RuntimeError("json_schema not supported")
        return _fake_completion('Вот ответ:\n```json\n{"bik": "044525225"}\n```')

    monkeypatch.setattr(client._client.chat.completions, "create", create)
    assert client.extract("текст").parsed_data == {"bik": "044525225"}
    assert len(calls) == 2


def test_yandexgpt_requires_credentials(monkeypatch):
    from app.llm.yandex_client import YandexGPTClient

    monkeypatch.setattr(settings, "yandex_api_key", "")
    with pytest.raises(LLMError):
        YandexGPTClient()


def test_pipeline_survives_llm_failure(tmp_path, monkeypatch):
    import shutil
    from pathlib import Path

    import app.services.pipeline_service as ps
    from app.llm.base import BaseLLMClient

    class Failing(BaseLLMClient):
        def extract(self, text, prompt_version="v1"):
            raise LLMError("quota exceeded")

    monkeypatch.setattr(ps, "_build_llm_client", Failing)
    pdf = tmp_path / "sample.pdf"
    shutil.copy(Path(__file__).parent / "fixtures" / "sample_requisites.pdf", pdf)
    result = ps.run_pipeline(pdf, "sample.pdf")
    assert result.data.inn == "7744012347"
    assert any("LLM unavailable" in w for w in result.warnings)


def test_build_llm_client_yandex_without_keys_is_mock(monkeypatch):
    import app.services.pipeline_service as ps
    from app.llm.mock_client import MockLLMClient

    monkeypatch.setattr(settings, "llm_provider", "yandex")
    monkeypatch.setattr(settings, "yandex_api_key", "")
    assert isinstance(ps._build_llm_client(), MockLLMClient)
