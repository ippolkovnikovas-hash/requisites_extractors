"""
Проверка полного наименования организации.

Организационно-правовая форма намеренно не требуется: наименование может быть
иностранным или записанным без ОПФ, и блокировать генерацию из-за этого нельзя.
Проверяется только то, что в поле вообще осмысленный текст, а не число или
одиночный символ.
"""

from app.core.utils import collapse_whitespace
from app.schemas.validation import FieldValidation

_MIN_LENGTH = 2


def validate_company_name(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(valid=True, is_missing=True, raw_value=value)

    normalized = collapse_whitespace(value)

    def _fail(reason: str) -> FieldValidation:
        return FieldValidation(
            valid=False, raw_value=value, normalized_value=normalized, reason=reason
        )

    if normalized.isdigit():
        return _fail("наименование состоит только из цифр (digits only)")

    if len(normalized) < _MIN_LENGTH:
        return _fail(f"наименование слишком короткое (too short): «{normalized}»")

    return FieldValidation(valid=True, raw_value=value, normalized_value=normalized)
