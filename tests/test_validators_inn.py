"""Unit-тесты валидатора ИНН."""
import pytest
from app.validators.inn_validator import validate_inn


@pytest.mark.parametrize("value", [
    "7744012347",   # валидный 10-значный
    "500100732259", # валидный 12-значный ИП
])
def test_inn_valid(value):
    result = validate_inn(value)
    assert result.valid, f"Expected valid INN: {value}, got: {result.reason}"


@pytest.mark.parametrize("value,reason_part", [
    (None,           "null"),
    ("",             "null"),
    ("123abc456",    "non-digit"),
    ("1234567890",   "checksum"),   # неверная контрольная сумма
    ("12345",        "length"),
    ("12345678901234", "length"),
])
def test_inn_invalid(value, reason_part):
    result = validate_inn(value)
    assert not result.valid
    assert reason_part in result.reason
