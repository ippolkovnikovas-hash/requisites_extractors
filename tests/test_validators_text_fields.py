"""
Unit-тесты текстовых валидаторов: company_name, short_name, bank_name,
ceo_position, ceo_fio_full, ceo_fio_short.

Общая схема для всех: None/""/строка из пробелов -> is_missing=True, valid=True.
Ни один hard error не завязан на конкретную ОПФ/должность/отчество; bank_name
не делает сетевых запросов и не сверяется со справочником.
"""
import pytest

from app.validators.bank_name_validator import validate_bank_name
from app.validators.ceo_validator import (
    validate_ceo_fio_full,
    validate_ceo_fio_short,
    validate_ceo_position,
)
from app.validators.company_name_validator import validate_company_name
from app.validators.short_name_validator import validate_short_name

# ── validate_company_name ────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [
    "Общество с ограниченной ответственностью Ромашка",  # с ОПФ
    "Ромашка Trading Corp",                                # без ОПФ вообще
    "ИП Иванов Иван Иванович",
])
def test_company_name_valid(value):
    result = validate_company_name(value)
    assert result.valid, f"expected valid company_name: {value!r}, got: {result.reason}"
    assert not result.is_missing


@pytest.mark.parametrize("value", [None, "", "   "])
def test_company_name_missing_variants(value):
    result = validate_company_name(value)
    assert result.valid
    assert result.is_missing
    assert result.raw_value == value


def test_company_name_digits_only_is_hard_error():
    result = validate_company_name("1234567")
    assert not result.valid
    assert not result.is_missing
    assert "digits" in result.reason


def test_company_name_too_short_is_hard_error():
    result = validate_company_name("Ё")
    assert not result.valid
    assert "short" in result.reason


def test_company_name_normalizes_whitespace():
    result = validate_company_name("  Ромашка   Инк  ")
    assert result.valid
    assert result.normalized_value == "Ромашка Инк"
    assert result.raw_value == "  Ромашка   Инк  "


# ── validate_short_name ──────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [
    "ООО Ромашка",
    'АО "Север"',
    "ИП Иванов И.И.",
    "Ромашка",  # без ОПФ вообще
])
def test_short_name_valid(value):
    result = validate_short_name(value)
    assert result.valid, f"expected valid short_name: {value!r}, got: {result.reason}"
    assert not result.is_missing


@pytest.mark.parametrize("value", [None, "", "   "])
def test_short_name_missing_variants(value):
    result = validate_short_name(value)
    assert result.valid
    assert result.is_missing


@pytest.mark.parametrize("value", ["ООО", "АО", "ПАО", "ЗАО"])
def test_short_name_opf_only_is_warning(value):
    result = validate_short_name(value)
    assert result.valid
    assert not result.is_missing
    assert result.warning is not None
    assert "названия" in result.warning


def test_short_name_ip_alone_is_not_warning():
    result = validate_short_name("ИП")
    assert result.valid
    assert result.warning is None


@pytest.mark.parametrize("value", ['ООО «Ромашка»', 'ООО "Ромашка"'])
def test_short_name_valid_regardless_of_quote_style(value):
    result = validate_short_name(value)
    assert result.valid
    assert result.warning is None


# ── validate_bank_name ───────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [
    "ПАО Сбербанк",
    'ПАО "Сбербанк"',
    'АО "Альфа-Банк"',
    "Банк ВТБ (ПАО)",
    "Филиал ПАО Сбербанк в г. Москве",
    "Дополнительный офис №1 ПАО Сбербанк",
    "Отделение 1 Банка России",
    "Центральный банк Российской Федерации (Банк России)",
    "РКЦ",
    "ГРКЦ",
    "ГУ Банка России",
])
def test_bank_name_valid(value):
    result = validate_bank_name(value)
    assert result.valid, f"expected valid bank_name: {value!r}"
    assert not result.is_missing
    assert result.warning is None


@pytest.mark.parametrize("value", [None, "", "   "])
def test_bank_name_missing_variants(value):
    result = validate_bank_name(value)
    assert result.valid
    assert result.is_missing


def test_bank_name_digits_only_is_warning():
    result = validate_bank_name("12345")
    assert result.valid
    assert not result.is_missing
    assert result.warning is not None
    assert "цифр" in result.warning


def test_bank_name_normalizes_whitespace():
    result = validate_bank_name("  ПАО   Сбербанк  ")
    assert result.valid
    assert result.normalized_value == "ПАО Сбербанк"
    assert result.raw_value == "  ПАО   Сбербанк  "


# ── validate_ceo_position ────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [
    "Генеральный директор",
    "Директор",
    "Исполнительный директор",
    "Управляющий",
    "Президент",
    "Председатель правления",
    "Председатель",
    "Руководитель",
    "Индивидуальный предприниматель",
    "Конкурсный управляющий",
    "Временный управляющий",
    "Ликвидатор",
    "Председатель ликвидационной комиссии",
    "Директор филиала",
    "Главный врач",
    "Ректор",
])
def test_ceo_position_valid_typical(value):
    result = validate_ceo_position(value)
    assert result.valid, f"expected valid ceo_position: {value!r}"
    assert result.warning is None


def test_ceo_position_valid_atypical_text_not_blocked():
    """Должность не входит в типовой список — не ошибка и не warning: нет whitelist."""
    result = validate_ceo_position("Финансовый директор по развитию")
    assert result.valid
    assert result.warning is None


@pytest.mark.parametrize("value", [None, "", "   "])
def test_ceo_position_missing_variants(value):
    result = validate_ceo_position(value)
    assert result.valid
    assert result.is_missing


def test_ceo_position_looks_like_phone_is_warning():
    result = validate_ceo_position("+7 495 123-45-67")
    assert result.valid
    assert result.warning is not None
    assert "телефон" in result.warning


def test_ceo_position_looks_like_email_is_warning():
    result = validate_ceo_position("info@example.ru")
    assert result.valid
    assert result.warning is not None
    assert "email" in result.warning


# ── validate_ceo_fio_full ────────────────────────────────────────────────────

def test_ceo_fio_full_valid_with_patronymic():
    result = validate_ceo_fio_full("Иванов Иван Иванович")
    assert result.valid
    assert result.warning is None


def test_ceo_fio_full_valid_without_patronymic_no_warning():
    """Отсутствие отчества — не ошибка и не warning."""
    result = validate_ceo_fio_full("Иванов Иван")
    assert result.valid
    assert result.warning is None


def test_ceo_fio_full_valid_latin_name():
    result = validate_ceo_fio_full("Smith John")
    assert result.valid
    assert result.warning is None


@pytest.mark.parametrize("value", [
    "Петров-Водкин Кузьма",
    "О'Брайен Джон",
])
def test_ceo_fio_full_valid_with_hyphen_and_apostrophe(value):
    result = validate_ceo_fio_full(value)
    assert result.valid, f"expected valid ceo_fio_full: {value!r}"
    assert result.warning is None


@pytest.mark.parametrize("value", [None, "", "   "])
def test_ceo_fio_full_missing_variants(value):
    result = validate_ceo_fio_full(value)
    assert result.valid
    assert result.is_missing


def test_ceo_fio_full_single_token_is_warning():
    result = validate_ceo_fio_full("Иванов")
    assert result.valid
    assert result.warning is not None
    assert "фамили" in result.warning


def test_ceo_fio_full_normalizes_multiple_spaces():
    result = validate_ceo_fio_full("Иванов   Иван    Иванович")
    assert result.valid
    assert result.normalized_value == "Иванов Иван Иванович"
    assert result.raw_value == "Иванов   Иван    Иванович"


# ── validate_ceo_fio_short ───────────────────────────────────────────────────

@pytest.mark.parametrize("value", [
    "Иванов И.И.",
    "Иванов И. И.",
    "Иванов И",
    "Иванов И.",
    "O'Brian J.",
    "Петров-Водкин К.",
])
def test_ceo_fio_short_valid(value):
    result = validate_ceo_fio_short(value)
    assert result.valid, f"expected valid ceo_fio_short: {value!r}, got warning: {result.warning}"
    assert result.warning is None


@pytest.mark.parametrize("value", [None, "", "   "])
def test_ceo_fio_short_missing_variants(value):
    result = validate_ceo_fio_short(value)
    assert result.valid
    assert result.is_missing


def test_ceo_fio_short_unmatched_pattern_is_warning():
    result = validate_ceo_fio_short("Иван Иванов Иванович")
    assert result.valid
    assert result.warning is not None
    assert "формат" in result.warning
