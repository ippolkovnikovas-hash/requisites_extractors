"""Тесты Mock LLM клиента."""
from app.llm.mock_client import MockLLMClient


def test_mock_returns_extraction_result():
    client = MockLLMClient()
    result = client.extract("любой текст")
    assert result.model_name == "mock"
    assert result.provider == "mock"


def test_mock_all_fields_none():
    client = MockLLMClient()
    result = client.extract("текст")
    assert result.parsed_data["inn"] is None
    assert result.parsed_data["ogrn"] is None
    assert len(result.parsed_data) == 16


def test_mock_raw_response_is_valid_json():
    import json
    client = MockLLMClient()
    result = client.extract("текст")
    parsed = json.loads(result.raw_response)
    assert isinstance(parsed, dict)


def test_mock_prompt_version_passed():
    client = MockLLMClient()
    result = client.extract("текст", prompt_version="v2")
    assert result.prompt_version == "v2"


def test_mock_parsed_data_is_copy():
    client = MockLLMClient()
    r1 = client.extract("a")
    r2 = client.extract("b")
    r1.parsed_data["inn"] = "modified"
    assert r2.parsed_data["inn"] is None
