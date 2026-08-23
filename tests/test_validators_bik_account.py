"""Unit-тесты валидаторов БИК и счетов."""
import pytest
from app.schemas.validation import FieldValidation
from app.validators.bik_validator import validate_bik
from app.validators.account_validator import (
    validate_account,
    validate_cross_bik_corr,
    account_control_key_ok,
)
from app.validators.cross_field_validator import validate_bik_account_consistency


def test_bik_valid():
    result = validate_bik("044525225")
    assert result.valid
    assert result.warning is None


@pytest.mark.parametrize("value,reason_part", [
    (None,        "null"),
    ("",          "null"),
    ("12345",     "length"),
])
def test_bik_invalid(value, reason_part):
    result = validate_bik(value)
    assert not result.valid
    assert reason_part in result.reason


def test_bik_null_is_missing_not_invalid_value():
    """Отсутствие значения помечается is_missing — отдельно от 'введено, но неверно'."""
    result = validate_bik(None)
    assert not result.valid
    assert result.is_missing


def test_bik_nonstandard_prefix_is_warning():
    """Раньше было жёсткой ошибкой — теперь предупреждение, не блокирует."""
    result = validate_bik("124525225")
    assert result.valid
    assert not result.is_missing
    assert result.warning is not None
    assert "04" in result.warning


@pytest.mark.parametrize("value,expected", [
    ("О44525225", "044525225"),   # кириллическая О
    ("0I452522I", "014525221"),   # I → 1 (позиции 2 и 9)
    ("044 525 225", "044525225"), # пробелы — не фолдинг, просто форматирование
])
def test_bik_ocr_confusables_normalized(value, expected):
    result = validate_bik(value)
    assert result.normalized_value == expected
    assert result.raw_value == value


def test_bik_ocr_fold_does_not_hide_leftover_garbage():
    """После узкой O/I-подмены остаток недопустимых символов — жёсткая ошибка, не отбрасывается молча."""
    result = validate_bik("04452522Ж")
    assert not result.valid
    assert "non-digit" in result.reason


def test_checking_account_valid():
    result = validate_account("40702810000000012345", "checking")
    assert result.valid
    assert result.warning is None


def test_checking_account_invalid_length():
    result = validate_account("4070281000000001234", "checking")
    assert not result.valid
    assert "length" in result.reason


def test_checking_account_non_digit_after_normalization_is_hard_error():
    result = validate_account("4070281000000001234Ж", "checking")
    assert not result.valid
    assert "non-digit" in result.reason


def test_cross_bik_corr_valid():
    result = validate_cross_bik_corr("044525225", "30101810400000000225")
    assert result is None  # None = нет ошибки


def test_cross_bik_corr_mismatch():
    result = validate_cross_bik_corr("044525225", "30101810400000000999")
    assert result is not None
    assert "mismatch" in result


def test_correspondent_account_valid():
    result = validate_account("30101810400000000225", "correspondent")
    assert result.valid
    assert result.warning is None


def test_checking_account_wrong_prefix_is_warning():
    """Раньше было жёсткой ошибкой — теперь предупреждение, не блокирует генерацию."""
    result = validate_account("30101810400000000225", "checking")
    assert result.valid
    assert not result.is_missing
    assert result.warning is not None
    assert "40" in result.warning


def test_correspondent_account_wrong_prefix_is_warning():
    result = validate_account("40702810000000012345", "correspondent")
    assert result.valid
    assert result.warning is not None
    assert "30" in result.warning


def test_unknown_account_type():
    result = validate_account("40702810000000012345", "savings")
    assert not result.valid
    assert "unknown" in result.reason


# ── Контрольный ключ БИК↔счёт ────────────────────────────────────────────────
# Документ: «Порядок расчёта контрольного ключа в номере лицевого счёта», № 515 от 08.09.1997.
#
#   CHECKING-вектор (БИК[6:9]): БИК 049805746, счёт 40602810700000000025.
#   Источник: https://normativ.kontur.ru/document?moduleId=1&documentId=24444
#
#   RKC-вектор ("0"+БИК[4:6]): БИК 040305000, счёт 40102810100000010001.
#   Источник: https://zakonbase.ru/content/part/140340
#
# Проверочные векторы зафиксированы по публичным публикациям текста документа;
# контрольный ключ используется только как warning.

def test_account_control_key_checking_valid_vector():
    """БИК[6:9]-правило (расчётный счёт). БИК 049805746 + счёт 40602810700000000025."""
    assert account_control_key_ok("049805746", "40602810700000000025", "checking") is True


def test_account_control_key_checking_negative_vector():
    """Та же пара с одной изменённой последней цифрой счёта — ключ не сходится."""
    assert account_control_key_ok("049805746", "40602810700000000026", "checking") is False


def test_account_control_key_correspondent_valid_vector():
    """0+БИК[4:6]-правило (корр. счёт). БИК 040305000 + счёт 40102810100000010001."""
    assert account_control_key_ok("040305000", "40102810100000010001", "correspondent") is True


def test_account_control_key_correspondent_negative_vector():
    assert account_control_key_ok("040305000", "40102810100000010002", "correspondent") is False


def test_account_control_key_wrong_significant_bik_digits_fails():
    """Другой БИК (те же длины) с той же парой счёта — ключ не должен случайно сойтись."""
    assert account_control_key_ok("049805747", "40602810700000000025", "checking") is False


# ── validate_bik_account_consistency: warning-only wrapper ──────────────────

def test_bik_account_consistency_matching_pair_no_warning():
    bik_result = validate_bik("049805746")
    account_result = validate_account("40602810700000000025", "checking")
    warning = validate_bik_account_consistency(bik_result, account_result, "checking")
    assert warning is None


def test_bik_account_consistency_mismatch_is_warning_not_error():
    bik_result = validate_bik("049805746")
    account_result = validate_account("40602810700000000026", "checking")
    warning = validate_bik_account_consistency(bik_result, account_result, "checking")
    assert warning is not None
    assert isinstance(warning, str)
    # Само по себе несовпадение ключа не должно портить valid счёта/БИК по отдельности
    assert account_result.valid
    assert bik_result.valid


def test_bik_account_consistency_correspondent_mismatch_is_warning():
    bik_result = validate_bik("040305000")
    account_result = validate_account("40102810100000010002", "correspondent")
    warning = validate_bik_account_consistency(bik_result, account_result, "correspondent")
    assert warning is not None


def test_bik_account_consistency_skipped_when_bik_invalid():
    """БИК не проходит базовую форматную проверку — контрольный ключ не считается вовсе."""
    bik_result = validate_bik("12345")  # неверная длина — жёсткая ошибка
    account_result = validate_account("40602810700000000025", "checking")
    warning = validate_bik_account_consistency(bik_result, account_result, "checking")
    assert warning is None


def test_bik_account_consistency_skipped_when_bik_missing():
    bik_result = validate_bik(None)
    account_result = validate_account("40602810700000000025", "checking")
    warning = validate_bik_account_consistency(bik_result, account_result, "checking")
    assert warning is None


def test_bik_account_consistency_skipped_when_account_invalid():
    bik_result = validate_bik("049805746")
    account_result = validate_account("406028107000000000", "checking")  # неверная длина
    warning = validate_bik_account_consistency(bik_result, account_result, "checking")
    assert warning is None
