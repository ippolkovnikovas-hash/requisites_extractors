"""
Проверка наименования банка.

Справочника банков в проекте нет и не будет: сверка со списком ЦБ означала бы
сетевой запрос с реквизитами, что запрещено. Поэтому валидатор максимально
мягкий — жёстких ошибок нет вовсе.

Наименования банков крайне разнородны: «ПАО Сбербанк», «Банк ВТБ (ПАО)»,
«Филиал ПАО Сбербанк в г. Москве», «Отделение 1 Банка России», «РКЦ», «ГРКЦ»,
«ГУ Банка России». Любая попытка требовать в них слово «банк» отсекла бы
законные значения.

Единственное предупреждение — если в поле одни цифры: почти наверняка туда
попал БИК или номер счёта.
"""

from app.core.utils import collapse_whitespace
from app.schemas.validation import FieldValidation

_WARNING = "наименование банка состоит только из цифр — похоже, попал БИК или счёт"


def validate_bank_name(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(valid=True, is_missing=True, raw_value=value)

    normalized = collapse_whitespace(value)

    digits_only = normalized.replace(" ", "").isdigit()

    return FieldValidation(
        valid=True,
        raw_value=value,
        normalized_value=normalized,
        warning=_WARNING if digits_only else None,
    )
