"""Unit-тесты валидаторов БИК и счетов."""
import pytest
from app.validators.bik_validator import validate_bik
from app.validators.account_validator import validate_account, validate_cross_bik_corr


def test_bik_valid():
    assert validate_bik("044525225").valid


@pytest.mark.parametrize("value,reason_part", [
    (None,        "null"),
    ("",          "null"),
    ("12345",     "length"),
    ("124525225", "04"),   # не начинается на 04
])
def test_bik_invalid(value, reason_part):
    result = validate_bik(value)
    assert not result.valid
    assert reason_part in result.reason


def test_checking_account_valid():
    assert validate_account("40702810000000012345", "checking").valid


def test_checking_account_invalid_length():
    result = validate_account("4070281000000001234", "checking")
    assert not result.valid


def test_cross_bik_corr_valid():
    result = validate_cross_bik_corr("044525225", "30101810400000000225")
    assert result is None  # None = нет ошибки


def test_cross_bik_corr_mismatch():
    result = validate_cross_bik_corr("044525225", "30101810400000000999")
    assert result is not None
    assert "mismatch" in result



def test_correspondent_account_valid():
    assert validate_account("30101810400000000225", "correspondent").valid


def test_checking_starts_with_40():
    result = validate_account("30101810400000000225", "checking")
    assert not result.valid
    assert "40" in result.reason


def test_unknown_account_type():
    result = validate_account("40702810000000012345", "savings")
    assert not result.valid
    assert "unknown" in result.reason
