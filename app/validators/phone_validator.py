"""
Проверка телефона.

Никаких сетевых вызовов и определения оператора: только разбор строки.

Поле может содержать несколько номеров через `,`, `;` или перенос строки —
каждый разбирается независимо. В `normalized_value` номера всегда объединяются
через `", "`, каким бы разделитель ни был в исходном значении.

Для каждого кандидата (после снятия форматирования и отделения добавочного):
  - 11 цифр, начинается на 7 или 8 — российский номер, без предупреждения;
  - 7-15 цифр в любом другом виде — валидно, но с предупреждением
    «нероссийский»; наличие или отсутствие «+» роли не играет;
  - меньше 7, больше 15 цифр или цифр нет вовсе — жёсткая ошибка для всего
    поля.

`raw_value` никогда не подменяется: «8» приводится к «+7» только в
`normalized_value`.
"""

import re

from app.schemas.validation import FieldValidation

_SEPARATORS = re.compile(r"[,;\n]")

# Добавочный номер в конце: «доб. 123», «доб 123», «ext. 123», «ext123»,
# «x123», «#123».
_EXTENSION = re.compile(r"(?:доб\.?|ext\.?|x|#)\s*(\d+)\s*$", re.IGNORECASE)

_MIN_DIGITS = 7
_MAX_DIGITS = 15
_RU_LENGTH = 11
_RU_PREFIXES = ("7", "8")

_FOREIGN_WARNING = "номер не похож на российский (нероссийский формат) — проверьте"


def validate_phone(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(valid=True, is_missing=True, raw_value=value)

    candidates = [part.strip() for part in _SEPARATORS.split(value)]
    candidates = [part for part in candidates if part]

    if not candidates:
        return FieldValidation(valid=True, is_missing=True, raw_value=value)

    normalized_parts: list[str] = []
    has_foreign = False

    for candidate in candidates:
        main, extension = _split_extension(candidate)
        digits = re.sub(r"\D", "", main)

        if not (_MIN_DIGITS <= len(digits) <= _MAX_DIGITS):
            return FieldValidation(
                valid=False,
                raw_value=value,
                normalized_value=None,
                reason=(
                    f"телефон «{candidate}» не разобран: ожидается от "
                    f"{_MIN_DIGITS} до {_MAX_DIGITS} цифр, найдено {len(digits)}"
                ),
            )

        if len(digits) == _RU_LENGTH and digits[0] in _RU_PREFIXES:
            normalized = "+7" + digits[1:]
        else:
            normalized = "+" + digits
            has_foreign = True

        if extension:
            normalized = f"{normalized} доб. {extension}"

        normalized_parts.append(normalized)

    return FieldValidation(
        valid=True,
        raw_value=value,
        normalized_value=", ".join(normalized_parts),
        warning=_FOREIGN_WARNING if has_foreign else None,
    )


def _split_extension(candidate: str) -> tuple[str, str | None]:
    """Отделяет добавочный номер от основного, если он указан в конце."""
    match = _EXTENSION.search(candidate)
    if not match:
        return candidate, None
    return candidate[: match.start()], match.group(1)
