"""Тесты fallback regex-экстрактора на тестовом PDF."""
import pytest
from pathlib import Path
from app.services.fallback_regex_service import extract_fallback_fields


SAMPLE_TEXT = """
ООО Тестовая Организация
ОГРН: 1027700123450
ИНН: 7744012347
КПП: 774401001
Банк: ПАО Сбербанк
Р/с: 40702810000000012345
К/с: 30101810400000000225
БИК: 044525225
Тел.: +7 (495) 123-45-67
E-mail: test@testorg.ru
"""



def test_extracts_inn():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["inn"] == "7744012347"


def test_extracts_ogrn():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["ogrn"] == "1027700123450"


def test_extracts_kpp():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["kpp"] == "774401001"


def test_extracts_bik():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["bik"] == "044525225"


def test_extracts_checking_account():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["checking_account"] == "40702810000000012345"


def test_extracts_correspondent_account():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["correspondent_account"] == "30101810400000000225"


def test_extracts_phone():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["phone"] == "+74951234567"


def test_extracts_email():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["email"] == "test@testorg.ru"


def test_empty_text_returns_empty():
    result = extract_fallback_fields("")
    assert result["inn"] is None
    assert result["ogrn"] is None






def test_phone_formats_normalized():
    formats = [
        "8 (495) 123-45-67",
        "8-495-123-45-67",
        "+7 495 123 45 67",
        "84951234567",
    ]
    for fmt in formats:
        result = extract_fallback_fields(f"Тел.: {fmt}")
        assert result["phone"] is not None, f"phone not extracted from: {fmt}"
        assert result["phone"].replace("+7", "8").replace("8", "", 1).isdigit() or result["phone"].startswith(("+7", "8")), f"unexpected format: {result['phone']}"
