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
