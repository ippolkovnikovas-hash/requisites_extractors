"""
Unit-тесты валидатора телефона.

Контракт: raw_value (исходное значение, никогда не меняется, показывается в
review-форме), normalized_value (канонический вид, несколько номеров
объединяются через ", " независимо от исходного разделителя в raw_value),
valid, is_missing, warning, reason.

None/""/пробелы -> is_missing=True, valid=True.

Поле может содержать несколько номеров через "," ";" или перенос строки —
каждый разбирается независимо, не склеивается.

Для каждого кандидата (после снятия форматирования и добавочного номера
доб./доб/ext./ext/x/#):
  - 11 цифр, начинается на 7 или 8 -> валиден, без warning;
  - 7-15 цифр, но не российский шаблон (наличие "+" не имеет значения) ->
    valid=True, warning содержит "нероссийск";
  - короче 7 или длиннее 15 цифр, либо цифр вообще нет -> hard error
    (reason содержит "телефон") для всего поля.

Нет сетевых вызовов, нет определения оператора/владельца номера.
"""

import pytest

from app.validators.phone_validator import validate_phone

# ── Российские форматы ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        "+79161234567",
        "89161234567",
        "79161234567",
    ],
)
def test_phone_valid_ru_formats(value):
    result = validate_phone(value)
    assert result.valid, f"expected valid RU phone: {value!r}, got: {result.reason}"
    assert not result.is_missing
    assert result.warning is None


@pytest.mark.parametrize("value", [None, "", "   "])
def test_phone_missing_variants(value):
    result = validate_phone(value)
    assert result.valid
    assert result.is_missing
    assert result.warning is None
    assert result.raw_value == value


def test_phone_valid_with_spaces_parens_dashes():
    result = validate_phone("+7 (916) 123-45-67")
    assert result.valid
    assert result.warning is None
    assert result.normalized_value == "+79161234567"


def test_phone_valid_with_extension_dob():
    result = validate_phone("+7 (495) 123-45-67 доб. 123")
    assert result.valid
    assert result.warning is None
    assert "123" in result.normalized_value
    assert result.raw_value == "+7 (495) 123-45-67 доб. 123"


@pytest.mark.parametrize(
    "value",
    [
        "+74951234567 доб 123",
        "+74951234567 доб. 123",
        "+74951234567 ext. 123",
        "+74951234567 ext123",
        "+74951234567x123",
        "+74951234567 #123",
    ],
)
def test_phone_valid_with_extension_variants(value):
    result = validate_phone(value)
    assert (
        result.valid
    ), f"expected valid phone with extension: {value!r}, got: {result.reason}"
    assert result.warning is None
    assert "123" in result.normalized_value


# ── Несколько номеров в одном поле ───────────────────────────────────────────


def test_phone_multiple_ru_numbers_comma_separated():
    result = validate_phone("+79161234567, 89261234567")
    assert result.valid
    assert result.warning is None
    assert "+79161234567" in result.normalized_value
    assert "+79261234567" in result.normalized_value


def test_phone_multiple_ru_numbers_semicolon_separated():
    result = validate_phone("+79161234567; 89261234567")
    assert result.valid
    assert result.warning is None
    assert "+79161234567" in result.normalized_value
    assert "+79261234567" in result.normalized_value


def test_phone_multiple_ru_numbers_newline_separated():
    result = validate_phone("+79161234567\n89261234567")
    assert result.valid
    assert result.warning is None
    assert "+79161234567" in result.normalized_value
    assert "+79261234567" in result.normalized_value


def test_phone_normalized_value_uses_comma_separator_for_multiple():
    """Независимо от разделителя в raw_value, normalized_value всегда через ", "."""
    result = validate_phone("+79161234567; 89261234567")
    assert result.normalized_value == "+79161234567, +79261234567"
    assert result.raw_value == "+79161234567; 89261234567"


def test_phone_ru_plus_international_mixed_is_warning():
    result = validate_phone("+79161234567, +442071234567")
    assert result.valid
    assert result.warning is not None
    assert "нероссийск" in result.warning
    assert "+79161234567" in result.normalized_value


# ── Международные номера — warning, не ошибка, наличие "+" не имеет значения ──


@pytest.mark.parametrize(
    "value",
    [
        "+442071234567",  # Великобритания
        "+12025551234",  # США
    ],
)
def test_phone_international_with_plus_is_warning(value):
    result = validate_phone(value)
    assert (
        result.valid
    ), f"expected valid (warning) international phone: {value!r}, got: {result.reason}"
    assert result.warning is not None
    assert "нероссийск" in result.warning


def test_phone_international_without_plus_is_warning():
    """Международный номер без '+' — тоже warning, а не hard error."""
    result = validate_phone("442071234567")
    assert result.valid
    assert result.warning is not None
    assert "нероссийск" in result.warning


# ── Hard error: не 7-15 цифр или текст без цифр ──────────────────────────────


def test_phone_too_short_is_hard_error():
    result = validate_phone("12345")
    assert not result.valid
    assert "телефон" in result.reason


def test_phone_too_long_is_hard_error():
    result = validate_phone("1234567890123456")  # 16 цифр
    assert not result.valid
    assert "телефон" in result.reason


def test_phone_random_text_without_digit_run_is_hard_error():
    result = validate_phone("просто текст без цифр")
    assert not result.valid
    assert "телефон" in result.reason


# ── OCR-устойчивость ──────────────────────────────────────────────────────────


def test_phone_ocr_broken_spacing_still_valid():
    result = validate_phone("+7 916 1 2 3-45-67")
    assert result.valid
    assert result.warning is None
    assert result.normalized_value == "+79161234567"


# ── 8-800 и мобильные ─────────────────────────────────────────────────────────


def test_phone_toll_free_8800_valid():
    result = validate_phone("88001234567")
    assert result.valid
    assert result.warning is None


def test_phone_mobile_valid():
    result = validate_phone("+79261234567")
    assert result.valid
    assert result.warning is None


# ── raw_value никогда не подменяется скрытно ─────────────────────────────────


def test_phone_raw_value_never_silently_replaces_8_with_plus7():
    result = validate_phone("89161234567")
    assert result.raw_value == "89161234567"
    assert result.normalized_value == "+79161234567"
