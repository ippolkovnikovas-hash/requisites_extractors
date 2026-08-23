"""Unit-тесты валидатора ОГРН."""
import pytest
from app.validators.ogrn_validator import validate_ogrn


@pytest.mark.parametrize("value", [
    "1027700123450",   # валидный 13-значный
])
def test_ogrn_valid(value):
    result = validate_ogrn(value)
    assert result.valid, f"Expected valid OGRN: {value}, got: {result.reason}"


@pytest.mark.parametrize("value,reason_part", [
    (None,    "null"),
    ("",      "null"),
    ("12345", "length"),
    ("1027700123451", "checksum"),
])
def test_ogrn_invalid(value, reason_part):
    result = validate_ogrn(value)
    assert not result.valid
    assert reason_part in result.reason


def test_ogrn_rejects_okpo_8_digits():
    """8-значное число — ОКПО, не ОГРН."""
    from app.validators.ogrn_validator import validate_ogrn
    r = validate_ogrn("12345678")
    assert not r.valid
    assert "OKPO/OKTMO" in r.reason

def test_ogrn_rejects_oktmo_11_digits():
    """11-значное число — ОКТМО, не ОГРН."""
    from app.validators.ogrn_validator import validate_ogrn
    r = validate_ogrn("12345678901")
    assert not r.valid
    assert "OKPO/OKTMO" in r.reason

def test_ogrn_rejects_10_digits():
    """10-значное число — ОКПО ЮЛ, не ОГРН."""
    from app.validators.ogrn_validator import validate_ogrn
    r = validate_ogrn("1234567890")
    assert not r.valid
    assert "OKPO/OKTMO" in r.reason


def test_ogrn_null_is_missing_not_invalid_value():
    result = validate_ogrn(None)
    assert not result.valid
    assert result.is_missing


def test_ogrn_wrong_checksum_is_not_missing():
    result = validate_ogrn("1027700123451")
    assert not result.valid
    assert not result.is_missing


@pytest.mark.parametrize("value,expected_digits", [
    ("1О27700123450", "1027700123450"),   # кириллическая О → 0
    ("1027700I23450", "1027700123450"),   # I → 1
    ("1027 700123450", "1027700123450"),  # пробел — форматирование, не фолдинг
])
def test_ogrn_ocr_confusables_normalized(value, expected_digits):
    result = validate_ogrn(value)
    assert result.normalized_value == expected_digits


def test_ogrn_valid_15_digit_ogrnip():
    """ОГРНИП — 15 цифр, отдельная контрольная сумма (модуль 13)."""
    from app.validators.ogrn_validator import validate_ogrn
    # 15-значный валидный ОГРНИП (модуль 13): 304500116000157
    result = validate_ogrn("304500116000157")
    assert result.valid, f"expected valid OGRNIP, got: {result.reason}"


def test_ogrn_invalid_15_digit_checksum():
    from app.validators.ogrn_validator import validate_ogrn
    result = validate_ogrn("304500116000158")
    assert not result.valid
    assert "checksum" in result.reason
