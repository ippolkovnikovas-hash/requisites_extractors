"""Unit-тесты валидатора КПП.

КПП НЕ имеет контрольной суммы (ни в проекте, ни в природе) — только структурная
проверка: 9 символов, первые 4 — цифры, 5-6 — цифры или латинские буквы, последние 3 — цифры.
"""
import pytest

from app.validators.kpp_validator import validate_kpp


@pytest.mark.parametrize("value", [
    "774401001",
    "770101001",
    "7744AB001",   # 5-6 позиция — латинские буквы (обособленное подразделение/спецкатегория)
])
def test_kpp_valid(value):
    result = validate_kpp(value)
    assert result.valid, f"expected valid KPP: {value}, got: {result.reason}"


@pytest.mark.parametrize("value,reason_part", [
    (None,      "null"),
    ("",        "null"),
    ("12345",   "length"),
    ("12345678901", "length"),
    ("77440100Ж", "format"),   # недопустимый символ вне разрешённой (5-6) позиции
    ("77Ж401001", "format"),   # буква в позиции, где должна быть цифра (1-4)
])
def test_kpp_invalid(value, reason_part):
    result = validate_kpp(value)
    assert not result.valid
    assert reason_part in result.reason


def test_kpp_null_is_missing_not_invalid_value():
    result = validate_kpp(None)
    assert not result.valid
    assert result.is_missing


def test_kpp_wrong_format_is_not_missing():
    """Введённое, но неверное значение — это не 'пусто', блокирует без confirm_invalid."""
    result = validate_kpp("12345")
    assert not result.valid
    assert not result.is_missing


def test_kpp_does_not_fold_ocr_confusables_in_letter_positions():
    """КПП не подменяет O/I на цифры — буквы в 5-6 позиции могут быть законными."""
    result = validate_kpp("7744OI001")  # O/I оставлены как есть, не свёрнуты в 0/1
    assert result.valid
    assert result.normalized_value == "7744OI001"


@pytest.mark.parametrize("value,expected", [
    ("7744 01001", "774401001"),   # пробел убран форматированием
    ("7744-01001", "774401001"),   # дефис убран форматированием
])
def test_kpp_strips_formatting_only(value, expected):
    result = validate_kpp(value)
    assert result.valid
    assert result.normalized_value == expected
