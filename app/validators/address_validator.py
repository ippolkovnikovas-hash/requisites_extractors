"""
Проверка адреса — общая для юридического и почтового.

Контракт и логика у обоих полей совпадают полностью, поэтому отдельных функций
нет. Валидатор не сравнивает юридический адрес с почтовым: их совпадение или
различие — нормальная ситуация, а не ошибка.

Работает только на эвристиках: ни ФИАС, ни КЛАДР, ни геокодирования, ни сети.
Поэтому **жёсткой ошибки у этого валидатора нет вообще** — максимум
предупреждение «не похоже на адрес». Решение всегда за человеком в
review-форме.

Логика предупреждения:

- Сильный признак (любого одного достаточно) — улица/проспект/переулок и
  прочие типы улиц, населённый пункт, регион.
- Слабые признаки — почтовый индекс, офис/помещение/квартира/корпус/строение,
  связка «дом» + номер. Поодиночке и почти в любых сочетаниях их
  недостаточно.
- Единственное исключение: «дом» + номер вместе с индексом снимают
  предупреждение и без сильного признака.

Почтовый индекс сам по себе желателен, но не обязателен: его отсутствие не
создаёт предупреждения (CLAUDE.md).
"""

import re

from app.core.utils import collapse_whitespace
from app.schemas.validation import FieldValidation

# ── Сильные признаки ────────────────────────────────────────────────────────

_STREET = re.compile(
    r"(?:^|[\s.,])(?:ул|улица|просп|проспект|пр-?кт|пер|переулок|проезд|ш|шоссе"
    r"|б-?р|бульвар|наб|набережная|пл|площадь|тракт|аллея|линия|туп|тупик)"
    r"(?:$|[\s.,])",
    re.IGNORECASE,
)

_SETTLEMENT = re.compile(
    r"(?:^|[\s.,])(?:г|гор|город|пос|посёлок|поселок|пгт|с|село|дер|деревня"
    r"|ст-?ца|станица|мкр|микрорайон|рп)(?:$|[\s.,])",
    re.IGNORECASE,
)

_FEDERAL_CITY = re.compile(
    r"\b(?:Москва|Санкт-Петербург|Севастополь)\b", re.IGNORECASE
)

_REGION = re.compile(
    r"(?:^|[\s.,])(?:обл|область|край|респ|республика|автономн\w*\s+округ"
    r"|автономн\w*\s+область|АО|округ|район|р-н)(?:$|[\s.,])",
    re.IGNORECASE,
)

# ── Слабые признаки ─────────────────────────────────────────────────────────

_POSTAL_INDEX = re.compile(r"\b\d{6}\b")

_HOUSE = re.compile(
    r"(?:^|[\s.,])(?:д|дом|вл|владение)\.?\s*\d",
    re.IGNORECASE,
)

_WARNING = "значение не похоже на адрес — проверьте"


def validate_address(value: str | None) -> FieldValidation:
    if value is None or not value.strip():
        return FieldValidation(valid=True, is_missing=True, raw_value=value)

    normalized = collapse_whitespace(value)

    has_strong = bool(
        _STREET.search(normalized)
        or _SETTLEMENT.search(normalized)
        or _FEDERAL_CITY.search(normalized)
        or _REGION.search(normalized)
    )

    has_index = bool(_POSTAL_INDEX.search(normalized))
    has_house = bool(_HOUSE.search(normalized))

    # Единственное послабление среди слабых признаков: «дом + номер» вместе с
    # индексом достаточно однозначно указывает на адрес.
    looks_like_address = has_strong or (has_house and has_index)

    return FieldValidation(
        valid=True,
        raw_value=value,
        normalized_value=normalized,
        warning=None if looks_like_address else _WARNING,
    )
