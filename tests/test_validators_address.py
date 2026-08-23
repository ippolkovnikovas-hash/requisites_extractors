"""
Unit-тесты валидатора адреса (используется одинаково для legal_address и
postal_address — контракт и логика полностью совпадают, отдельных функций нет).

Правила (без внешних справочников ФИАС/КЛАДР, без геокодирования, без сети):

Сильные признаки (любой один достаточен для отсутствия warning):
  - улица/проспект/переулок/проезд/шоссе/бульвар/набережная/площадь;
  - явный город/населённый пункт (включая города федерального значения);
  - регион (область/край/республика/автономный округ).

Слабые признаки (сами по себе, по одному или в любой комбинации кроме
специального случая ниже, НЕ снимают warning):
  - индекс (6 цифр);
  - офис/помещение/квартира/корпус/строение/литера;
  - связка "дом"/"д." + номер;
  - отдельное числовое значение вне перечисленного выше.

Единственное исключение: связка "дом/д." + номер СОВМЕСТНО с индексом —
warning не ставится, даже без сильного признака.

Иначе: valid=True всегда (hard error у этого валидатора нет вообще, reason
всегда None), warning содержит "адрес", если ни одно из условий выше не
выполнено.
"""

import pytest

from app.validators.address_validator import validate_address

# ── Валидные адреса (сильный признак присутствует) ──────────────────────────


def test_address_valid_full_with_index():
    result = validate_address("119019, г. Москва, ул. Волхонка, д. 15")
    assert result.valid
    assert not result.is_missing
    assert result.warning is None
    assert result.reason is None


def test_address_valid_without_index():
    result = validate_address("г. Москва, ул. Волхонка, д. 15")
    assert result.valid
    assert result.warning is None


def test_address_valid_partial_city_and_street_only():
    result = validate_address("г. Москва, ул. Тверская")
    assert result.valid
    assert result.warning is None


# ── Отсутствие значения — необязательное поле ────────────────────────────────


@pytest.mark.parametrize("value", [None, "", "   "])
def test_address_missing_variants(value):
    result = validate_address(value)
    assert result.valid
    assert result.is_missing
    assert result.warning is None
    assert result.raw_value == value


# ── Мусор/не-адрес вместо адреса ─────────────────────────────────────────────


def test_address_email_in_field_is_warning():
    result = validate_address("info@example.ru")
    assert result.valid
    assert not result.is_missing
    assert result.warning is not None
    assert "адрес" in result.warning


def test_address_phone_in_field_is_warning():
    result = validate_address("+7 495 123-45-67")
    assert result.valid
    assert result.warning is not None
    assert "адрес" in result.warning


def test_address_account_number_in_field_is_warning():
    result = validate_address("40702810000000012345")
    assert result.valid
    assert result.warning is not None
    assert "адрес" in result.warning


def test_address_fio_without_address_words_is_warning():
    result = validate_address("Иванов Иван Иванович")
    assert result.valid
    assert result.warning is not None
    assert "адрес" in result.warning


def test_address_generic_garbage_no_entity_is_warning():
    result = validate_address("asdkjh qwerty zxc")
    assert result.valid
    assert result.warning is not None
    assert "адрес" in result.warning


# ── Совпадение/различие юр. и почт. адреса — валидатор не сравнивает поля ────


def test_address_legal_and_postal_equal_values_both_valid_independently():
    value = "г. Москва, ул. Волхонка, д. 15"
    legal_result = validate_address(value)
    postal_result = validate_address(value)
    assert legal_result.valid and postal_result.valid
    assert legal_result.warning is None
    assert postal_result.warning is None


def test_address_legal_and_postal_different_values_both_valid_independently():
    legal_result = validate_address("г. Москва, ул. Волхонка, д. 15")
    postal_result = validate_address("г. Санкт-Петербург, Невский проспект, д. 1")
    assert legal_result.valid and postal_result.valid
    assert legal_result.warning is None
    assert postal_result.warning is None


# ── Нормализация: только пробелы/переносы, без перестановки частей ──────────


def test_address_normalizes_whitespace_without_reordering_parts():
    result = validate_address("г. Москва,\n  ул.   Волхонка,\nд. 15")
    assert result.valid
    assert result.normalized_value == "г. Москва, ул. Волхонка, д. 15"
    assert result.raw_value == "г. Москва,\n  ул.   Волхонка,\nд. 15"


# ── Никогда не hard error ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        "info@example.ru",
        "40702810000000012345",
        "asdkjh qwerty zxc",
        "123456",
        "офис 12",
    ],
)
def test_address_never_produces_hard_error(value):
    result = validate_address(value)
    assert result.valid is True
    assert result.reason is None


# ── Слабые признаки поодиночке — недостаточно, warning ставится ─────────────


def test_address_single_weak_signal_office_only_is_warning():
    result = validate_address("офис 12")
    assert result.valid
    assert result.warning is not None
    assert "адрес" in result.warning


def test_address_single_weak_signal_index_only_is_warning():
    result = validate_address("123456")
    assert result.valid
    assert result.warning is not None
    assert "адрес" in result.warning


def test_address_single_weak_signal_house_number_only_is_warning():
    result = validate_address("д. 15")
    assert result.valid
    assert result.warning is not None
    assert "адрес" in result.warning


# ── Сильный + слабый — сильного одного достаточно ───────────────────────────


def test_address_strong_city_plus_weak_house_no_warning():
    result = validate_address("г. Москва, д. 15")
    assert result.valid
    assert result.warning is None


def test_address_strong_street_plus_weak_office_no_warning():
    result = validate_address("ул. Тверская, офис 12")
    assert result.valid
    assert result.warning is None


# ── Единственное исключение среди слабых: дом+номер вместе с индексом ───────


def test_address_house_number_plus_index_no_warning():
    """Связка "дом/д." + номер вместе с индексом — специальное исключение,
    достаточно и без сильного признака."""
    result = validate_address("119019, д. 15")
    assert result.valid
    assert result.warning is None


def test_address_office_plus_index_still_warning():
    """Офис + индекс — это НЕ то же исключение, что дом+индекс: два прочих
    слабых признака вместе по-прежнему недостаточны."""
    result = validate_address("офис 12, 119019")
    assert result.valid
    assert result.warning is not None
    assert "адрес" in result.warning
