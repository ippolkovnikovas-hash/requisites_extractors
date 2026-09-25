from app.schemas.validation import FieldValidation

_OKPO_LENGTHS = {8, 10}
_OKTMO_LENGTHS = {8, 11}
_CLASSIFIER_LENGTHS = _OKPO_LENGTHS | _OKTMO_LENGTHS  # 8, 10, 11


def _ogrn_check(digits_str: str, mod: int) -> bool:
    n = int(digits_str[:-1])
    check = n % mod % 10
    return check == int(digits_str[-1])


def validate_ogrn(value: str | None) -> FieldValidation:
    if not value:
        return FieldValidation(valid=False, value=value, reason="field is null")

    v = value.strip().replace(" ", "")

    if not v.isdigit():
        return FieldValidation(valid=False, value=value, reason="contains non-digit chars")

    if len(v) in _CLASSIFIER_LENGTHS:
        return FieldValidation(
            valid=False, value=value,
            reason=f"likely OKPO/OKTMO classifier, not OGRN (length={len(v)})"
        )

    if len(v) == 13:
        if not _ogrn_check(v, 11):
            return FieldValidation(valid=False, value=value, reason="invalid OGRN checksum")
        return FieldValidation(valid=True, value=v)

    if len(v) == 15:
        if not _ogrn_check(v, 13):
            return FieldValidation(valid=False, value=value, reason="invalid OGRNIP checksum")
        return FieldValidation(valid=True, value=v)

    return FieldValidation(
        valid=False, value=value,
        reason=f"wrong length: {len(v)}, expected 13 or 15"
    )
