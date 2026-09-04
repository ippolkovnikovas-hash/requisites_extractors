"""
Замер качества извлечения: field-level accuracy вместо `fill_rate`.

`RequisitesData.fill_rate()` считает долю непустых полей — она не знает,
верное это значение или нет. Склейка на 200 символов из regex-слоя (см.
разбор пайплайна, эпики Э13–Э15) засчитывалась как «поле заполнено» наравне
с правильным значением. Здесь сравнение идёт значение за значением против
заранее подготовленного человеком эталона.

Требует реальных документов: синтетические фикстуры проекта составлены под
текущие правила валидации и не показывают, где pipeline на самом деле
ошибается на живых сканах. Эталон и документы в Git не попадают — см.
`scripts/measure_accuracy.py`.
"""

from app.schemas.requisites import RequisitesData


class FieldOutcome:
    """Пять исходов сравнения одного поля одного документа."""

    MATCH = "match"
    MISMATCH = "mismatch"
    MISSING = "missing"
    CORRECT_EMPTY = "correct_empty"
    FALSE_POSITIVE = "false_positive"


def _normalize_for_comparison(value: str | None) -> str | None:
    """
    Сравнение терпимо только к форматированию — схлопыванию пробелов по
    краям и внутри значения. Регистр и содержимое не трогаются: сравнение не
    должно быть мягче собственной нормализации проекта, иначе оно скрывало
    бы реальные расхождения.
    """
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None


def compare_field(expected: str | None, actual: str | None) -> str:
    """
    Сравнивает одно поле: значение из эталона против значения, которое отдал
    pipeline.
    """
    expected_n = _normalize_for_comparison(expected)
    actual_n = _normalize_for_comparison(actual)

    if expected_n is None:
        return (
            FieldOutcome.FALSE_POSITIVE
            if actual_n is not None
            else FieldOutcome.CORRECT_EMPTY
        )

    if actual_n is None:
        return FieldOutcome.MISSING

    return FieldOutcome.MATCH if expected_n == actual_n else FieldOutcome.MISMATCH


def compare_document(
    expected: RequisitesData, actual: RequisitesData
) -> dict[str, str]:
    """Сравнивает все 16 полей одного документа. Возвращает {поле: исход}."""
    return {
        field: compare_field(getattr(expected, field), getattr(actual, field))
        for field in RequisitesData.model_fields
    }


def aggregate_field_accuracy(
    per_document_outcomes: list[dict[str, str]],
) -> dict[str, dict[str, float | int | None]]:
    """
    Точность по каждому полю отдельно.

    `correct_empty` в знаменатель не входит: поле, отсутствующее почти во
    всех документах, иначе выглядело бы «стопроцентно точным», хотя по нему
    ни разу не проверялось, находит ли pipeline значение, когда оно
    действительно есть, — ровно та проблема, из-за которой `fill_rate` не
    годится для этого замера.
    """
    # Набор полей берём из самих исходов, а не из RequisitesData: функция не
    # обязана знать про конкретную схему реквизитов, ей достаточно словарей
    # {поле: исход} — то, что и производит compare_document().
    fields: set[str] = set()
    for doc in per_document_outcomes:
        fields.update(doc)

    report: dict[str, dict[str, float | int | None]] = {}

    for field in fields:
        outcomes = [doc[field] for doc in per_document_outcomes if field in doc]
        match = outcomes.count(FieldOutcome.MATCH)
        mismatch = outcomes.count(FieldOutcome.MISMATCH)
        missing = outcomes.count(FieldOutcome.MISSING)
        correct_empty = outcomes.count(FieldOutcome.CORRECT_EMPTY)
        false_positive = outcomes.count(FieldOutcome.FALSE_POSITIVE)

        denominator = match + mismatch + missing
        accuracy = round(match / denominator, 4) if denominator else None

        report[field] = {
            "match": match,
            "mismatch": mismatch,
            "missing": missing,
            "correct_empty": correct_empty,
            "false_positive": false_positive,
            "accuracy": accuracy,
        }

    return report


def overall_accuracy(
    field_report: dict[str, dict[str, float | int | None]],
) -> float | None:
    """
    Точность по всем полям сразу, взвешенная по числу документов с
    непустым эталоном — не среднее по полям, иначе редкое поле с одним
    измерением весило бы столько же, сколько ИНН, измеренный на всей
    выборке.
    """
    total_match = sum(r["match"] for r in field_report.values())
    total_denominator = sum(
        r["match"] + r["mismatch"] + r["missing"] for r in field_report.values()
    )
    return round(total_match / total_denominator, 4) if total_denominator else None
