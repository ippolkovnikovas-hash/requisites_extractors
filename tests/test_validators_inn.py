"""Unit-тесты валидатора ИНН."""

import pytest

from app.validators.inn_validator import validate_inn


@pytest.mark.parametrize(
    "value",
    [
        "7744012347",  # валидный 10-значный
        "500100732259",  # валидный 12-значный ИП
    ],
)
def test_inn_valid(value):
    result = validate_inn(value)
    assert result.valid, f"Expected valid INN: {value}, got: {result.reason}"


@pytest.mark.parametrize(
    "value,reason_part",
    [
        (None, "null"),
        ("", "null"),
        ("123abc456", "non-digit"),
        ("1234567890", "checksum"),  # неверная контрольная сумма
        ("12345", "length"),
        ("12345678901234", "length"),
    ],
)
def test_inn_invalid(value, reason_part):
    result = validate_inn(value)
    assert not result.valid
    assert reason_part in result.reason


def test_inn_null_is_missing_not_invalid_value():
    result = validate_inn(None)
    assert not result.valid
    assert result.is_missing


def test_inn_wrong_checksum_is_not_missing():
    result = validate_inn("1234567890")
    assert not result.valid
    assert not result.is_missing


@pytest.mark.parametrize(
    "value,expected_digits",
    [
        ("774401234О", "7744012340"),  # кириллическая О → 0 (последняя цифра)
        ("7744OI2347", "7744012347"),  # O→0, I→1 внутри номера
        ("7744 012347", "7744012347"),  # пробел — просто форматирование, не фолдинг
    ],
)
def test_inn_ocr_confusables_normalized(value, expected_digits):
    result = validate_inn(value)
    assert result.normalized_value == expected_digits


def test_inn_ocr_fold_still_hard_errors_on_leftover_garbage():
    result = validate_inn("774401234Ж")
    assert not result.valid
    assert "non-digit" in result.reason
