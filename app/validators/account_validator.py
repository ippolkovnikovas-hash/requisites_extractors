"""
Проверка банковских счетов — 20 цифр.

По правилам проекта (CLAUDE.md): неверная длина или недопустимые символы после
нормализации — жёсткая ошибка; нетипичный префикс (`40` для расчётного, `30`
для корреспондентского) — только предупреждение.

Здесь же реализован расчёт контрольного ключа по методике ЦБ РФ «Порядок
расчёта контрольного ключа в номере лицевого счёта» № 515 от 08.09.1997.
Результат этой проверки используется только как warning и никогда не блокирует
генерацию документа — обёртка живёт в `cross_field_validator`.
"""

from app.core.utils import fold_numeric_confusables
from app.schemas.validation import FieldValidation

_ACCOUNT_LENGTH = 20
_EXPECTED_PREFIX = {
    "checking": "40",
    "correspondent": "30",
}

# Весовые коэффициенты из методики № 515: 23 позиции —
# 3 цифры «условного номера банка» + 20 цифр счёта.
_CONTROL_KEY_WEIGHTS = [7, 1, 3] * 7 + [7, 1]

_FOLD_WARNING = "В значении заменены символы, похожие на цифры (O→0, I→1) — проверьте"


def validate_account(value: str | None, account_type: str) -> FieldValidation:
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

    if len(normalized) != _ACCOUNT_LENGTH:
        return _fail(f"wrong length: {len(normalized)}, expected {_ACCOUNT_LENGTH}")

    if account_type not in _EXPECTED_PREFIX:
        return _fail(f"unknown account type: {account_type}")

    expected_prefix = _EXPECTED_PREFIX[account_type]
    if not normalized.startswith(expected_prefix):
        warnings.append(
            f"нетипичный префикс счёта: ожидается «{expected_prefix}», "
            f"получено «{normalized[:2]}»"
        )

    return FieldValidation(
        valid=True,
        raw_value=value,
        normalized_value=normalized,
        warning="; ".join(warnings) if warnings else None,
    )


def account_control_key_ok(bik: str, account: str, account_type: str) -> bool:
    """
    Контрольный ключ счёта по методике ЦБ РФ № 515.

    Перед 20 цифрами счёта дописывается трёхзначный «условный номер банка»:
      - для счетов в кредитной организации (расчётный) — `БИК[6:9]`;
      - для счетов в подразделении ЦБ (корреспондентский) — `"0" + БИК[4:6]`.

    Ключ сходится, если сумма произведений (взятых по младшему разряду) всех 23
    цифр на весовые коэффициенты кратна 10.
    """
    if account_type == "checking":
        bank_code = bik[6:9]
    elif account_type == "correspondent":
        bank_code = "0" + bik[4:6]
    else:
        return False

    combined = bank_code + account
    if len(combined) != len(_CONTROL_KEY_WEIGHTS) or not combined.isdigit():
        return False

    checksum = sum(
        int(digit) * weight % 10
        for digit, weight in zip(combined, _CONTROL_KEY_WEIGHTS)
    )
    return checksum % 10 == 0


def validate_cross_bik_corr(
    bik: str | None, correspondent_account: str | None
) -> str | None:
    """
    Быстрая структурная сверка: последние 3 цифры БИК должны совпадать с
    разрядами 18-20 корреспондентского счёта.

    Это не контрольный ключ, а более грубая проверка. Возвращает текст
    расхождения или `None`.
    """
    if not bik or not correspondent_account:
        return None

    bik_clean, _ = fold_numeric_confusables(bik)
    ks_clean, _ = fold_numeric_confusables(correspondent_account)

    if not bik_clean.isdigit() or not ks_clean.isdigit():
        return None

    if len(bik_clean) != 9 or len(ks_clean) != _ACCOUNT_LENGTH:
        return None

    if ks_clean[17:20] != bik_clean[-3:]:
        return "BIK and correspondent account mismatch"

    return None
