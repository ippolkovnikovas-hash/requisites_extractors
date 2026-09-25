"""
Проверка сокращённого наименования организации.

Жёстких ошибок нет: сокращённое наименование бывает каким угодно, в том числе
без организационно-правовой формы и в любом стиле кавычек.

Единственное предупреждение — когда в поле осталась только ОПФ без самого
названия: типичный результат обрыва строки при OCR. «ИП» из этого правила
исключено: в связке с ФИО руководителя оно самодостаточно и часто встречается
в документах именно так.
"""

from app.core.utils import collapse_whitespace
from app.schemas.validation import FieldValidation

_OPF_ONLY = {"ООО", "ОАО", "ЗАО", "ПАО", "НАО", "АО", "НКО", "АНО", "ГУП", "МУП"}

_WARNING = "указана только организационно-правовая форма, без названия"


def validate_short_name(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(valid=True, is_missing=True, raw_value=value)

    normalized = collapse_whitespace(value)

    warning = _WARNING if normalized.upper() in _OPF_ONLY else None

    return FieldValidation(
        valid=True,
        raw_value=value,
        normalized_value=normalized,
        warning=warning,
    )
