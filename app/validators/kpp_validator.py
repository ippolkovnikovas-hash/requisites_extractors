from app.schemas.validation import FieldValidation


def validate_kpp(value: str | None) -> FieldValidation:
    if not value:
        return FieldValidation(valid=False, value=value, reason="field is null")

    v = value.strip().replace(" ", "")

    if not v.isdigit():
        return FieldValidation(valid=False, value=value, reason="contains non-digit chars")
    if len(v) != 9:
        return FieldValidation(valid=False, value=value, reason=f"wrong length: {len(v)}, expected 9")

    return FieldValidation(valid=True, value=v)
