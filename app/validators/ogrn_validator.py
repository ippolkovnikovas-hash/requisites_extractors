"""
Проверка ОГРН и ОГРНИП.

ОГРН   — 13 цифр, контрольная 13-я: остаток от деления первых 12 цифр на 11.
ОГРНИП — 15 цифр, контрольная 15-я: остаток от деления первых 14 цифр на 13.

Отдельно отсекаются классификаторы, которые OCR и LLM регулярно подставляют в
поле ОГРН: ОКПО (8 цифр для ИП и 10 для ЮЛ) и ОКТМО (11 цифр). Формально это
«неверная длина», но пользователю полезнее знать, что в поле попал другой код,
а не просто «не то количество цифр».
"""

from app.core.utils import fold_numeric_confusables
from app.schemas.validation import FieldValidation

# Длины кодов, которые чаще всего ошибочно попадают в поле ОГРН.
_CLASSIFIER_LENGTHS = {
    8: "OKPO (8-digit)",
    10: "OKPO (10-digit)",
    11: "OKTMO",
}

_FOLD_WARNING = "В значении заменены символы, похожие на цифры (O→0, I→1) — проверьте"


def validate_ogrn(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(
            valid=False, is_missing=True, raw_value=value, reason="field is null"
        )

    normalized, folded = fold_numeric_confusables(value)
    warning = _FOLD_WARNING if folded else None

    def _fail(reason: str) -> FieldValidation:
        return FieldValidation(
            valid=False,
            raw_value=value,
            normalized_value=normalized,
            reason=reason,
            warning=warning,
        )

    if not normalized.isdigit():
        return _fail("contains non-digit chars")

    length = len(normalized)

    if length in _CLASSIFIER_LENGTHS:
        return _fail(
            f"looks like OKPO/OKTMO, not OGRN: {length} digits "
            f"({_CLASSIFIER_LENGTHS[length]})"
        )

    if length == 13:
        if int(normalized[:12]) % 11 % 10 != int(normalized[12]):
            return _fail("invalid checksum (13-digit OGRN)")
    elif length == 15:
        if int(normalized[:14]) % 13 % 10 != int(normalized[14]):
            return _fail("invalid checksum (15-digit OGRNIP)")
    else:
        return _fail(f"wrong length: {length}, expected 13 or 15")

    return FieldValidation(
        valid=True,
        raw_value=value,
        normalized_value=normalized,
        warning=warning,
    )
