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



_KEY_WEIGHTS = [7, 1, 3] * 8
# БИК подразделений Банка России (РКЦ): счёт считается по номеру РКЦ, а не по 3 последним цифрам
_RKC_BIK_SUFFIXES = {"000", "001", "002"}


def validate_account_key(bik: str | None, account: str | None, account_type: str) -> bool | None:
    """
    Проверка контрольного ключа счёта по БИК (алгоритм Банка России).

    Возвращает True/False, либо None — если проверить нельзя (нет данных или неверный формат).
    Для расчётного счёта: 3 последние цифры БИК + номер счёта.
    Для корр. счёта (и счетов в РКЦ): "0" + 5-6 цифры БИК + номер счёта.
    Сумма младших разрядов произведений на веса 7,1,3,… должна оканчиваться на 0.
    """
    if not bik or not account:
        return None

    bik_clean = bik.strip().replace(" ", "")
    acc_clean = account.strip().replace(" ", "")
    if not (bik_clean.isdigit() and acc_clean.isdigit()):
        return None
    if len(bik_clean) != 9 or len(acc_clean) != 20:
        return None

    if account_type == "correspondent" or bik_clean[-3:] in _RKC_BIK_SUFFIXES:
        prefix = "0" + bik_clean[4:6]
    elif account_type == "checking":
        prefix = bik_clean[-3:]
    else:
        return None

    digits = prefix + acc_clean
    total = sum(int(d) * w % 10 for d, w in zip(digits, _KEY_WEIGHTS))
    return total % 10 == 0
