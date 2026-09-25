"""
Проверка БИК — 9 цифр.

По правилам проекта (CLAUDE.md): неверная длина или недопустимые символы после
нормализации — жёсткая ошибка; нетипичный префикс — только предупреждение.
Российские БИК начинаются на «04», но блокировать генерацию из-за префикса
нельзя: справочник ЦБ меняется, а пользователь видит исходное значение и решает
сам.
"""

from app.core.utils import fold_numeric_confusables
from app.schemas.validation import FieldValidation

_EXPECTED_PREFIX = "04"
_FOLD_WARNING = "В значении заменены символы, похожие на цифры (O→0, I→1) — проверьте"


def validate_bik(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(
            valid=False, is_missing=True, raw_value=value, reason="field is null"
        )

    normalized, folded = fold_numeric_confusables(value)
    warnings = [_FOLD_WARNING] if folded else []

    def _fail(reason: str) -> FieldValidation:
        return FieldValidation(
            valid=False,
            raw_value=value,
            normalized_value=normalized,
            reason=reason,
            warning="; ".join(warnings) if warnings else None,
        )

    if not normalized.isdigit():
        return _fail("contains non-digit chars")

    if len(normalized) != 9:
        return _fail(f"wrong length: {len(normalized)}, expected 9")

    if not normalized.startswith(_EXPECTED_PREFIX):
        warnings.append(
            f"нетипичный префикс БИК: ожидается «{_EXPECTED_PREFIX}», "
            f"получено «{normalized[:2]}»"
        )

    return FieldValidation(
        valid=True,
        raw_value=value,
        normalized_value=normalized,
        warning="; ".join(warnings) if warnings else None,
    )
