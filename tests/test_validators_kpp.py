"""Unit-тесты валидатора КПП."""
import pytest
from app.validators.kpp_validator import validate_kpp


@pytest.mark.parametrize("value", ["774401001", "770101001"])
def test_kpp_valid(value):
    assert validate_kpp(value).valid


@pytest.mark.parametrize("value,reason_part", [
    (None,      "null"),
    ("",        "null"),
    ("12345",   "length"),
    ("12345678901", "length"),
])
def test_kpp_invalid(value, reason_part):
    result = validate_kpp(value)
    assert not result.valid
    assert reason_part in result.reason
