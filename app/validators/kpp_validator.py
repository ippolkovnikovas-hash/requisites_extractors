"""
Структурная проверка КПП.

Контрольной суммы у КПП нет и не будет (см. CLAUDE.md) — проверяется только
структура: 9 символов, где
  позиции 1-4 — цифры (код налогового органа),
  позиции 5-6 — цифры или латинские буквы (причина постановки на учёт),
  позиции 7-9 — цифры (порядковый номер).

OCR-фолдинг здесь применять нельзя: `O` и `I` в позициях 5-6 могут быть
законными буквами, а не искажёнными нулём и единицей. Поэтому используется
только `strip_formatting()`, снимающий пробелы и дефисы.
"""

from app.core.utils import strip_formatting
from app.schemas.validation import FieldValidation

_LETTER_POSITIONS_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def validate_kpp(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(
            valid=False, is_missing=True, raw_value=value, reason="field is null"
        )

    # Регистр букв в позициях 5-6 — прозрачная нормализация, значение не меняется
    # по существу.
    normalized = strip_formatting(value).upper()

    def _fail(reason: str) -> FieldValidation:
        return FieldValidation(
            valid=False, raw_value=value, normalized_value=normalized, reason=reason
        )

    if len(normalized) != 9:
        return _fail(f"wrong length: {len(normalized)}, expected 9")

    if not normalized[:4].isdigit():
        return _fail("invalid format: positions 1-4 must be digits")

    for ch in normalized[4:6]:
        if not (ch.isdigit() or ch in _LETTER_POSITIONS_ALLOWED):
            return _fail(
                "invalid format: positions 5-6 must be digits or latin letters"
            )

    if not normalized[6:9].isdigit():
        return _fail("invalid format: positions 7-9 must be digits")

    return FieldValidation(valid=True, raw_value=value, normalized_value=normalized)
