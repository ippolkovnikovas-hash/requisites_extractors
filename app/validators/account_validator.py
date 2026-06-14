from app.schemas.validation import FieldValidation


def validate_account(value: str | None, account_type: str) -> FieldValidation:
    if not value:
        return FieldValidation(valid=False, value=value, reason="field is null")

    v = value.strip().replace(" ", "")

    if not v.isdigit():
        return FieldValidation(valid=False, value=value, reason="contains non-digit chars")

    if len(v) != 20:
        return FieldValidation(valid=False, value=value, reason=f"wrong length: {len(v)}, expected 20")

    if account_type == "checking":
        if not v.startswith("40"):
            return FieldValidation(
                valid=False,
                value=value,
                reason="checking account must start with 40",
            )
        return FieldValidation(valid=True, value=v)

    if account_type == "correspondent":
        if not v.startswith("30"):
            return FieldValidation(
                valid=False,
                value=value,
                reason="correspondent account must start with 30",
            )
        return FieldValidation(valid=True, value=v)

    return FieldValidation(valid=False, value=value, reason=f"unknown account type: {account_type}")


def validate_cross_bik_corr(bik: str | None, correspondent_account: str | None) -> str | None:
    if not bik or not correspondent_account:
        return None

    bik_clean = bik.strip().replace(" ", "")
    ks_clean = correspondent_account.strip().replace(" ", "")

    if not bik_clean.isdigit() or not ks_clean.isdigit():
        return None

    if len(bik_clean) != 9 or len(ks_clean) != 20:
        return None

    # Классическая проверка: последние 3 цифры БИК должны совпадать с 6-8 разрядами к/с
    if ks_clean[17:20] != bik_clean[-3:]:
        return "BIK and correspondent account mismatch"

    return None