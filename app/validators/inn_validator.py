"""
Алгоритмическая проверка ИНН по официальным правилам ФНС.
ИНН организации — 10 цифр, контрольная 10-я цифра.
ИНН ИП — 12 цифр, контрольные 11-я и 12-я цифры.
"""

from app.core.utils import fold_numeric_confusables
from app.schemas.validation import FieldValidation

_WEIGHTS_10 = [2, 4, 10, 3, 5, 9, 4, 6, 8]
_WEIGHTS_11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
_WEIGHTS_12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]

_FOLD_WARNING = "В значении заменены символы, похожие на цифры (O→0, I→1) — проверьте"


def _checksum(digits: list[int], weights: list[int]) -> int:
    return sum(d * w for d, w in zip(digits, weights)) % 11 % 10


def validate_inn(value: str | None) -> FieldValidation:
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

    digits = [int(c) for c in normalized]

    if len(digits) == 10:
        if _checksum(digits[:9], _WEIGHTS_10) != digits[9]:
            return _fail("invalid checksum (10-digit INN)")
    elif len(digits) == 12:
        if _checksum(digits[:10], _WEIGHTS_11) != digits[10]:
            return _fail("invalid checksum digit 11 (12-digit INN)")
        if _checksum(digits[:11], _WEIGHTS_12) != digits[11]:
            return _fail("invalid checksum digit 12 (12-digit INN)")
    else:
        return _fail(f"wrong length: {len(digits)}, expected 10 or 12")

    return FieldValidation(
        valid=True,
        raw_value=value,
        normalized_value=normalized,
        warning=warning,
    )
