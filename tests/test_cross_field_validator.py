"""
Unit-тесты кросс-полевых проверок app/validators/cross_field_validator.py.

Все функции возвращают str | None (текст warning или None), ничего не мутируют
и никогда не создают hard error — это дополнительные warning-источники для
validate_requisites(), а не отдельные валидаторы полей.

validate_bik_account_consistency() (БИК + р/с/к/с, контрольный ключ) здесь НЕ
тестируется — её 7 тестов уже есть в tests/test_validators_bik_account.py
(совпадение/несовпадение для обоих типов счёта, пропуск при
невалидном/отсутствующем БИК, пропуск при невалидном счёте).
"""
import pytest

from app.validators.cross_field_validator import (
    validate_ceo_fio_consistency,
    validate_inn_kpp_consistency,
)

# ── ИНН + КПП ─────────────────────────────────────────────────────────────────
# Warning только если ИНН существует, проходит validate_inn() и имеет 12 цифр,
# И КПП существует и проходит validate_kpp() по структурной проверке. Если КПП
# отсутствует или невалиден по формату — None (его собственная ошибка уже
# показана validate_kpp, дублировать шумом не нужно).

def test_inn_kpp_12digit_inn_with_valid_kpp_is_warning():
    result = validate_inn_kpp_consistency("500100732259", "774401001")
    assert result is not None
    assert isinstance(result, str)


def test_inn_kpp_10digit_inn_with_valid_kpp_no_warning():
    result = validate_inn_kpp_consistency("7744012347", "774401001")
    assert result is None


def test_inn_kpp_missing_kpp_no_warning():
    result = validate_inn_kpp_consistency("500100732259", None)
    assert result is None


def test_inn_kpp_missing_inn_no_warning():
    result = validate_inn_kpp_consistency(None, "774401001")
    assert result is None


def test_inn_kpp_invalid_checksum_inn_no_warning():
    """10 цифр, но неверная контрольная сумма — ИНН ненадёжен, cross-check не выполняется."""
    result = validate_inn_kpp_consistency("1234567890", "774401001")
    assert result is None


def test_inn_kpp_wrong_length_inn_no_warning():
    result = validate_inn_kpp_consistency("12345", "774401001")
    assert result is None


def test_inn_kpp_valid_inn_with_invalid_format_kpp_no_warning():
    """Валидный 12-значный ИНН, но КПП не проходит validate_kpp() по формату —
    его собственная ошибка уже видна отдельно, cross-check не добавляет шум."""
    result = validate_inn_kpp_consistency("500100732259", "12345")
    assert result is None


def test_inn_kpp_consistency_does_not_mutate_inputs():
    inn = "500100732259"
    kpp = "774401001"
    validate_inn_kpp_consistency(inn, kpp)
    assert inn == "500100732259"
    assert kpp == "774401001"


# ── Полное + краткое ФИО ──────────────────────────────────────────────────────

def test_ceo_fio_consistency_matching_surname_no_warning():
    result = validate_ceo_fio_consistency("Иванов Иван Иванович", "Иванов И.И.")
    assert result is None


def test_ceo_fio_consistency_mismatched_surname_is_warning():
    result = validate_ceo_fio_consistency("Иванов Иван Иванович", "Петров И.И.")
    assert result is not None


@pytest.mark.parametrize("fio_full,fio_short", [
    (None, "Иванов И.И."),
    ("Иванов Иван", None),
])
def test_ceo_fio_consistency_one_missing_no_warning(fio_full, fio_short):
    result = validate_ceo_fio_consistency(fio_full, fio_short)
    assert result is None


def test_ceo_fio_consistency_both_missing_no_warning():
    result = validate_ceo_fio_consistency(None, None)
    assert result is None


def test_ceo_fio_consistency_normalizes_case():
    result = validate_ceo_fio_consistency("иванов иван иванович", "ИВАНОВ И.И.")
    assert result is None


def test_ceo_fio_consistency_normalizes_whitespace():
    result = validate_ceo_fio_consistency("  Иванов   Иван Иванович", "Иванов И.И.")
    assert result is None


def test_ceo_fio_consistency_hyphenated_surname_matches():
    result = validate_ceo_fio_consistency("Петров-Водкин Кузьма", "Петров-Водкин К.")
    assert result is None


def test_ceo_fio_consistency_apostrophe_surname_matches():
    result = validate_ceo_fio_consistency("О'Брайен Джон", "О'Брайен Д.")
    assert result is None


def test_ceo_fio_consistency_short_with_two_initials_matches():
    result = validate_ceo_fio_consistency("Иванов Иван Иванович", "Иванов И. И.")
    assert result is None


def test_ceo_fio_consistency_short_with_one_initial_matches():
    result = validate_ceo_fio_consistency("Иванов Иван", "Иванов И.")
    assert result is None


def test_ceo_fio_consistency_foreign_names_match():
    result = validate_ceo_fio_consistency("Smith John", "Smith J.")
    assert result is None


def test_ceo_fio_consistency_does_not_mutate_inputs():
    fio_full = "Иванов Иван Иванович"
    fio_short = "Петров И.И."
    validate_ceo_fio_consistency(fio_full, fio_short)
    assert fio_full == "Иванов Иван Иванович"
    assert fio_short == "Петров И.И."
