"""
Алгоритмическая проверка ИНН по официальным правилам ФНС.
ИНН организации — 10 цифр, контрольная 10-я цифра.
ИНН ИП — 12 цифр, контрольные 11-я и 12-я цифры.
"""

from app.schemas.validation import FieldValidation


_WEIGHTS_10 = [2, 4, 10, 3, 5, 9, 4, 6, 8]
_WEIGHTS_11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
_WEIGHTS_12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]


def _checksum(digits: list[int], weights: list[int]) -> int:
    return sum(d * w for d, w in zip(digits, weights)) % 11 % 10


def validate_inn(value: str | None) -> FieldValidation:
    if not value:
        return FieldValidation(valid=False, value=value, reason="field is null")

    digits_str = value.strip().replace(" ", "")

    if not digits_str.isdigit():
        return FieldValidation(valid=False, value=value, reason="contains non-digit chars")

    digits = [int(c) for c in digits_str]

    if len(digits) == 10:
        if _checksum(digits[:9], _WEIGHTS_10) != digits[9]:
            return FieldValidation(valid=False, value=value, reason="invalid checksum (10-digit INN)")
        return FieldValidation(valid=True, value=digits_str)

    if len(digits) == 12:
        if _checksum(digits[:10], _WEIGHTS_11) != digits[10]:
            return FieldValidation(valid=False, value=value, reason="invalid checksum digit 11 (12-digit INN)")
        if _checksum(digits[:11], _WEIGHTS_12) != digits[11]:
            return FieldValidation(valid=False, value=value, reason="invalid checksum digit 12 (12-digit INN)")
        return FieldValidation(valid=True, value=digits_str)

    return FieldValidation(valid=False, value=value, reason=f"wrong length: {len(digits)}, expected 10 or 12")