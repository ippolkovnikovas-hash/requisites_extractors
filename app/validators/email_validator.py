"""
Синтаксическая проверка email.

Проверка исключительно структурная: никаких обращений к DNS, MX или SMTP —
приложение работает офлайн и не имеет права ходить в сеть с реквизитами.

Валидатор бинарный: у него нет warning-ветки вообще. Либо адрес разбирается,
либо это жёсткая ошибка.

Поле может содержать несколько адресов через `,`, `;` или перенос строки.
Каждый кандидат проверяется независимо; если хотя бы один не проходит формат —
невалидно всё поле, потому что в шаблон уйдёт строка целиком.

IDN/punycode не поддерживается: кириллица трактуется как обычный недопустимый
символ.
"""

import re

from app.schemas.validation import FieldValidation

_SEPARATORS = re.compile(r"[,;\n]")
_LOCAL_ALLOWED = re.compile(r"^[A-Za-z0-9._%+-]+$")
_DOMAIN_ALLOWED = re.compile(r"^[A-Za-z0-9.-]+$")


def validate_email(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(valid=True, is_missing=True, raw_value=value)

    candidates = [part.strip() for part in _SEPARATORS.split(value)]
    candidates = [part for part in candidates if part]

    if not candidates:
        return FieldValidation(valid=True, is_missing=True, raw_value=value)

    normalized_parts: list[str] = []
    for candidate in candidates:
        reason = _check_candidate(candidate)
        if reason:
            return FieldValidation(
                valid=False, raw_value=value, normalized_value=None, reason=reason
            )
        local, domain = candidate.rsplit("@", 1)
        normalized_parts.append(f"{local}@{domain.lower()}")

    return FieldValidation(
        valid=True,
        raw_value=value,
        normalized_value=", ".join(normalized_parts),
    )


def _check_candidate(candidate: str) -> str | None:
    """Возвращает текст жёсткой ошибки или None, если адрес корректен."""
    if candidate.count("@") != 1:
        return f"адрес «{candidate}» должен содержать ровно один символ «@»"

    local, domain = candidate.split("@", 1)

    if not local:
        return f"адрес «{candidate}»: пустая часть до @"
    if not domain:
        return f"адрес «{candidate}»: пустой домен после @"

    if not _LOCAL_ALLOWED.match(local) or not _DOMAIN_ALLOWED.match(domain):
        return f"адрес «{candidate}»: недопустимые символы"

    if "." not in domain:
        return f"адрес «{candidate}»: домен должен содержать точку"

    if local.startswith(".") or local.endswith(".") or ".." in local:
        return f"адрес «{candidate}»: недопустимая точка в local-part"

    if domain.startswith(".") or domain.endswith(".") or ".." in domain:
        return f"адрес «{candidate}»: недопустимая точка в домене"

    for label in domain.split("."):
        if label.startswith("-") or label.endswith("-"):
            return f"адрес «{candidate}»: дефис в начале или конце доменной метки"

    return None
