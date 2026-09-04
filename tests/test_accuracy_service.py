"""
Тесты замера качества извлечения: field-level accuracy вместо `fill_rate`.

`fill_rate` считает непустые поля — склейка на 200 символов из regex-слоя
засчитывается как «поле заполнено», хотя это не то значение, которое нужно
пользователю (см. ROADMAP, эпик Э11). Здесь сравнение идёт против заранее
подготовленного человеком эталона, значение за значением.
"""

import pytest

from app.schemas.requisites import RequisitesData
from app.services.accuracy_service import (
    FieldOutcome,
    aggregate_field_accuracy,
    compare_document,
    compare_field,
    overall_accuracy,
)

# ── compare_field ────────────────────────────────────────────────────────────


def test_compare_field_match():
    assert compare_field("7801234567", "7801234567") == FieldOutcome.MATCH


def test_compare_field_mismatch():
    assert compare_field("7801234567", "7801234568") == FieldOutcome.MISMATCH


def test_compare_field_missing_when_extractor_returned_nothing():
    """Эталон непустой, но pipeline не нашёл значение вовсе — это не то же
    самое, что найти неверное значение (разные причины, разные действия)."""
    assert compare_field("7801234567", None) == FieldOutcome.MISSING


def test_compare_field_correct_empty_when_both_absent():
    """Поле необязательно и в документе его действительно нет — pipeline
    ничего не придумал, это правильный результат, а не ошибка."""
    assert compare_field(None, None) == FieldOutcome.CORRECT_EMPTY


def test_compare_field_false_positive_when_extractor_hallucinated():
    """Эталон пуст (в документе поля нет), но pipeline что-то туда подставил —
    это опаснее, чем обычный mismatch: система придумала несуществующие
    данные."""
    assert compare_field(None, "ООО Ромашка") == FieldOutcome.FALSE_POSITIVE


def test_compare_field_ignores_pure_whitespace_differences():
    """Сравнение терпимо только к форматированию — лишним пробелам по краям
    и внутри, не к содержимому. Иначе сравнение получилось бы строже, чем
    собственная нормализация проекта."""
    assert compare_field("ООО  Ромашка", "ООО Ромашка ") == FieldOutcome.MATCH


def test_compare_field_empty_string_treated_as_absent():
    assert compare_field("", None) == FieldOutcome.CORRECT_EMPTY
    assert compare_field(None, "") == FieldOutcome.CORRECT_EMPTY


def test_compare_field_is_case_sensitive():
    """Регистр в наименованиях и адресах — часть содержимого, а не
    форматирование: искажение регистра должно засчитываться как ошибка."""
    assert compare_field("ООО Ромашка", "ооо ромашка") == FieldOutcome.MISMATCH


# ── compare_document ─────────────────────────────────────────────────────────


def test_compare_document_covers_all_sixteen_fields():
    expected = RequisitesData(inn="7801234567", company_name="ООО Ромашка")
    actual = RequisitesData(inn="7801234567", company_name="ООО Ромашка")

    outcomes = compare_document(expected, actual)

    assert set(outcomes) == set(RequisitesData.model_fields)
    assert outcomes["inn"] == FieldOutcome.MATCH
    assert outcomes["company_name"] == FieldOutcome.MATCH
    assert outcomes["kpp"] == FieldOutcome.CORRECT_EMPTY


# ── aggregate_field_accuracy ─────────────────────────────────────────────────


def test_aggregate_field_accuracy_computes_ratio_per_field():
    per_document = [
        {"inn": FieldOutcome.MATCH, "kpp": FieldOutcome.MATCH},
        {"inn": FieldOutcome.MISMATCH, "kpp": FieldOutcome.MATCH},
        {"inn": FieldOutcome.MATCH, "kpp": FieldOutcome.MATCH},
    ]

    report = aggregate_field_accuracy(per_document)

    assert report["inn"]["accuracy"] == pytest.approx(2 / 3, abs=1e-4)
    assert report["inn"]["match"] == 2
    assert report["inn"]["mismatch"] == 1
    assert report["kpp"]["accuracy"] == 1.0


def test_aggregate_field_accuracy_excludes_correct_empty_from_denominator():
    """
    Поле, отсутствующее в большинстве документов, не должно искусственно
    завышать точность: если эталон пуст почти во всех документах, «100%
    accuracy» ничего не говорит о том, находит ли pipeline это поле, когда
    оно действительно есть.
    """
    per_document = [
        {"phone": FieldOutcome.CORRECT_EMPTY},
        {"phone": FieldOutcome.CORRECT_EMPTY},
        {"phone": FieldOutcome.MATCH},
    ]

    report = aggregate_field_accuracy(per_document)

    assert report["phone"]["accuracy"] == 1.0
    assert report["phone"]["correct_empty"] == 2


def test_aggregate_field_accuracy_none_when_field_never_expected():
    """Если ни в одном документе поле не было заполнено в эталоне — точность
    неопределена (не 0, не 100%), это должно быть видно в отчёте отдельно."""
    per_document = [{"phone": FieldOutcome.CORRECT_EMPTY}]

    report = aggregate_field_accuracy(per_document)

    assert report["phone"]["accuracy"] is None


def test_aggregate_field_accuracy_counts_false_positives_separately():
    per_document = [
        {"kpp": FieldOutcome.FALSE_POSITIVE},
        {"kpp": FieldOutcome.CORRECT_EMPTY},
    ]

    report = aggregate_field_accuracy(per_document)

    assert report["kpp"]["false_positive"] == 1
    assert report["kpp"]["accuracy"] is None  # оба документа с пустым эталоном


# ── overall_accuracy ─────────────────────────────────────────────────────────


def test_overall_accuracy_weighted_across_fields():
    field_report = {
        "inn": {"match": 8, "mismatch": 2, "missing": 0},
        "kpp": {"match": 5, "mismatch": 0, "missing": 5},
    }
    assert overall_accuracy(field_report) == pytest.approx(13 / 20, abs=1e-4)


def test_overall_accuracy_none_when_nothing_to_measure():
    field_report = {"phone": {"match": 0, "mismatch": 0, "missing": 0}}
    assert overall_accuracy(field_report) is None
