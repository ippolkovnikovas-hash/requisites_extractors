"""
Проверка полей руководителя: должность, полное и краткое ФИО.

Списка допустимых должностей нет намеренно: должность руководителя бывает
какой угодно («Финансовый директор по развитию», «Главный врач», «Конкурсный
управляющий»), и whitelist только мешал бы. Предупреждение выдаётся лишь
тогда, когда в поле явно попало значение из другого поля — телефон или email.

Отсутствие отчества в полном ФИО не считается проблемой: у иностранных имён
его нет вовсе.

Жёстких ошибок ни у одного из трёх полей нет.
"""

import re

from app.core.utils import collapse_whitespace
from app.schemas.validation import FieldValidation

_EMAIL_LIKE = re.compile(r"\S+@\S+")
_MIN_PHONE_DIGITS = 7

# Фамилия: буквы, дефис, апостроф. Затем один-два инициала с точкой или без.
_NAME_CHARS = r"[A-Za-zА-Яа-яЁё'’\-]"
_INITIAL = r"[A-Za-zА-Яа-яЁё]\.?"
_SHORT_FIO = re.compile(
    rf"^{_NAME_CHARS}+\s+{_INITIAL}(?:\s*{_INITIAL})?$",
)

_POSITION_PHONE_WARNING = "в поле должности похоже на телефон — проверьте"
_POSITION_EMAIL_WARNING = "в поле должности похоже на email — проверьте"
_FIO_FULL_SINGLE_TOKEN_WARNING = (
    "указана только фамилия, без имени — проверьте полное ФИО"
)
_FIO_SHORT_FORMAT_WARNING = (
    "краткое ФИО не совпадает с форматом «Фамилия И.О.» — проверьте"
)


def validate_ceo_position(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(valid=True, is_missing=True, raw_value=value)

    normalized = collapse_whitespace(value)

    if _EMAIL_LIKE.search(normalized):
        warning = _POSITION_EMAIL_WARNING
    elif len(re.sub(r"\D", "", normalized)) >= _MIN_PHONE_DIGITS:
        warning = _POSITION_PHONE_WARNING
    else:
        warning = None

    return FieldValidation(
        valid=True, raw_value=value, normalized_value=normalized, warning=warning
    )


def validate_ceo_fio_full(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(valid=True, is_missing=True, raw_value=value)

    normalized = collapse_whitespace(value)
    warning = (
        _FIO_FULL_SINGLE_TOKEN_WARNING if len(normalized.split()) < 2 else None
    )

    return FieldValidation(
        valid=True, raw_value=value, normalized_value=normalized, warning=warning
    )


def validate_ceo_fio_short(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(valid=True, is_missing=True, raw_value=value)

    normalized = collapse_whitespace(value)
    warning = None if _SHORT_FIO.match(normalized) else _FIO_SHORT_FORMAT_WARNING

    return FieldValidation(
        valid=True, raw_value=value, normalized_value=normalized, warning=warning
    )
