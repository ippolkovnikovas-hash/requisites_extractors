"""Unit-тесты общих нормализаторов app/core/utils.py."""

import pytest

from app.core.utils import fold_numeric_confusables, strip_formatting


@pytest.mark.parametrize(
    "value,expected",
    [
        ("044 525 225", "044525225"),
        ("044-525-225", "044525225"),
        ("044 525 225", "044525225"),  # неразрывный пробел
        ("044\n525\t225", "044525225"),
        ("044–525225", "044525225"),  # en dash
        (None, None),
        ("", ""),
    ],
)
def test_strip_formatting(value, expected):
    assert strip_formatting(value) == expected


@pytest.mark.parametrize(
    "value,expected_digits,expected_folded",
    [
        ("044525225", "044525225", False),  # уже чистое — не тронуто
        ("О44525225", "044525225", True),  # кириллическая О → 0
        ("O44525225", "044525225", True),  # латинская O → 0
        ("0I4525225", "014525225", True),  # I → 1
        ("0l4525225", "014525225", True),  # строчная l → 1
        ("0|4525225", "014525225", True),  # вертикальная черта → 1
        ("044 525 225", "044525225", False),  # только пробелы — не считается фолдингом
        ("О44 525-225", "044525225", True),  # и то, и то
        (None, None, False),
    ],
)
def test_fold_numeric_confusables(value, expected_digits, expected_folded):
    normalized, folded = fold_numeric_confusables(value)
    assert normalized == expected_digits
    assert folded is expected_folded


def test_fold_numeric_confusables_does_not_touch_other_letters():
    """Символы, не входящие в узкий список подмен, остаются как есть (не обнуляются)."""
    normalized, folded = fold_numeric_confusables("04452522Ж")
    assert normalized == "04452522Ж"
    assert folded is False
