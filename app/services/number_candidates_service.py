"""
Выбор числовых реквизитов по кандидатам и контрольным суммам.

LLM и OCR ошибаются в цифрах, поэтому числа не берём из ответа модели «как есть»:
  1. Собираем из текста все последовательности цифр (с пробелами/дефисами внутри,
     с исправлением типичных OCR-подмен букв на цифры между цифрами).
  2. Для каждого поля оставляем кандидатов, прошедших валидатор (длина, контрольная сумма).
  3. Среди них выбираем стоящего рядом с нужной меткой («ИНН», «БИК», «р/с»…).
  4. Счета дополнительно сверяем с БИК по контрольному ключу ЦБ.
  5. Значение от LLM (hint) используется только как подсказка при равных кандидатах.
"""

import re
from dataclasses import dataclass

from app.validators.account_validator import validate_account, validate_account_key
from app.validators.bik_validator import validate_bik
from app.validators.inn_validator import validate_inn
from app.validators.kpp_validator import validate_kpp
from app.validators.ogrn_validator import validate_ogrn

NUMERIC_FIELDS = ("inn", "kpp", "ogrn", "bik", "checking_account", "correspondent_account")

# Максимальное расстояние (символов) от конца метки до начала числа
_MAX_LABEL_DISTANCE = 60

# Метки полей. Порядок важен: составные метки проверяются раньше простых.
# Значение — множество полей, к которым относится число после метки;
# пустое множество — «чужая» метка (классификаторы, реквизиты банка, телефон).
_LABELS: list[tuple[re.Pattern, frozenset[str]]] = [
    (re.compile(r"(?:ИНН|КПП|ОГРН)\s+банка", re.IGNORECASE), frozenset()),
    (re.compile(r"ИНН\s*/\s*КПП|ИНН\s*,\s*КПП|ИНН\s+КПП", re.IGNORECASE), frozenset({"inn", "kpp"})),
    (re.compile(r"ОГРН\s*ИП|ОГРНИП|ОГРН", re.IGNORECASE), frozenset({"ogrn"})),
    (re.compile(r"ИНН", re.IGNORECASE), frozenset({"inn"})),
    (re.compile(r"КПП", re.IGNORECASE), frozenset({"kpp"})),
    (re.compile(r"БИК", re.IGNORECASE), frozenset({"bik"})),
    (
        re.compile(
            r"к\s*/\s*с|к\s*\\\s*с|кор+\.?\s*/?\s*сч|кор+\.?\s+сч[её]т|корреспондентск\w*(?:\s+сч[её]т)?",
            re.IGNORECASE,
        ),
        frozenset({"correspondent_account"}),
    ),
    (
        re.compile(
            r"р\s*/\s*с(?:ч)?|р\s*\\\s*с|р/сч|расч\.?\s*/?\s*сч[её]т|расч[её]тн\w*(?:\s+сч[её]т)?"
            r"|сч[её]т\s*№|сч[её]т\s+получателя",
            re.IGNORECASE,
        ),
        frozenset({"checking_account"}),
    ),
    (
        re.compile(r"ОКПО|ОКТМО|ОКАТО|ОКВЭД|ОКОГУ|ОКФС|ОКОПФ|ОКОНХ|тел\w*|факс|моб\w*", re.IGNORECASE),
        frozenset(),
    ),
]

_FIELD_LENGTHS: dict[str, tuple[int, ...]] = {
    "inn": (10, 12),
    "kpp": (9,),
    "ogrn": (13, 15),
    "bik": (9,),
    "checking_account": (20,),
    "correspondent_account": (20,),
}

# Буквы, которые OCR путает с цифрами. Заменяем только между цифрами, длина текста не меняется.
_OCR_DIGIT_MAP = str.maketrans({
    "О": "0", "o": "0", "O": "0", "о": "0", "Q": "0",
    "l": "1", "I": "1", "|": "1", "і": "1",
    "З": "3", "з": "3",
    "Б": "6", "б": "6",
    "S": "5", "B": "8", "В": "8",
})
_OCR_CONFUSABLE_RE = re.compile(r"(?<=\d)[ОoOоQlI|іЗзБбSBВ](?=\d)")

# Цифровая группа и разделители внутри одного номера
_DIGIT_RUN_RE = re.compile(r"\d+(?:[ \-]\d+)*")


@dataclass(frozen=True)
class NumberCandidate:
    value: str
    start: int
    end: int


@dataclass(frozen=True)
class _Label:
    fields: frozenset[str]
    start: int
    end: int


def _fix_ocr_digits(text: str) -> str:
    return _OCR_CONFUSABLE_RE.sub(lambda m: m.group(0).translate(_OCR_DIGIT_MAP), text)


def find_digit_candidates(text: str) -> list[NumberCandidate]:
    """
    Все подходящие по длине числа из текста.
    Группа «1234 5678 90» даёт кандидатов из любых подряд идущих частей,
    поэтому и «4070 2810 …», и «7744012347 774401001» разбираются правильно.
    """
    wanted = {n for lengths in _FIELD_LENGTHS.values() for n in lengths}
    fixed = _fix_ocr_digits(text)
    result: list[NumberCandidate] = []
    seen: set[tuple[str, int]] = set()

    for run in _DIGIT_RUN_RE.finditer(fixed):
        groups = [(m.group(0), run.start() + m.start()) for m in re.finditer(r"\d+", run.group(0))]
        for i in range(len(groups)):
            value = ""
            for j in range(i, len(groups)):
                value += groups[j][0]
                if len(value) > 20:
                    break
                if len(value) in wanted:
                    start = groups[i][1]
                    end = groups[j][1] + len(groups[j][0])
                    if (value, start) not in seen:
                        seen.add((value, start))
                        result.append(NumberCandidate(value, start, end))
    return result


def _find_labels(text: str) -> list[_Label]:
    labels: list[_Label] = []
    taken: list[tuple[int, int]] = []
    for pattern, fields in _LABELS:
        for m in pattern.finditer(text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            labels.append(_Label(fields, m.start(), m.end()))
    labels.sort(key=lambda lb: lb.start)
    return labels


def _owning_label(
    labels: list[_Label], candidate: NumberCandidate, text: str
) -> _Label | None:
    """
    Ближайшая метка перед числом (не дальше _MAX_LABEL_DISTANCE).
    Метка владеет только «своими» числами: если между ней и кандидатом уже стоит
    другое число, значит у метки своё значение есть (составная «ИНН/КПП» — два числа).
    """
    owner = None
    for label in labels:
        if label.end > candidate.start:
            break
        owner = label
    if owner is None or candidate.start - owner.end > _MAX_LABEL_DISTANCE:
        return None
    between = text[owner.end:candidate.start]
    numbers_between = sum(
        1 for m in _DIGIT_RUN_RE.finditer(between) if len(re.sub(r"\D", "", m.group(0))) >= 5
    )
    if numbers_between >= max(1, len(owner.fields)):
        return None
    return owner


def _is_valid(field: str, value: str) -> bool:
    if len(value) not in _FIELD_LENGTHS[field]:
        return False
    match field:
        case "inn":
            return validate_inn(value).valid
        case "kpp":
            return validate_kpp(value).valid
        case "ogrn":
            return validate_ogrn(value).valid
        case "bik":
            return validate_bik(value).valid
        case "checking_account":
            return validate_account(value, "checking").valid
        case "correspondent_account":
            return validate_account(value, "correspondent").valid
    return False


@dataclass(frozen=True)
class _Scored:
    value: str
    labeled: bool
    distance: int
    position: int


def _field_candidates(
    field: str, candidates: list[NumberCandidate], labels: list[_Label], text: str
) -> list[_Scored]:
    scored: list[_Scored] = []
    for c in candidates:
        if not _is_valid(field, c.value):
            continue
        owner = _owning_label(labels, c, text)
        if owner is not None and field not in owner.fields:
            continue  # число принадлежит другой метке (ОКПО, ИНН банка, телефон…)
        labeled = owner is not None
        distance = c.start - owner.end if owner else _MAX_LABEL_DISTANCE + 1
        scored.append(_Scored(c.value, labeled, distance, c.start))
    return scored


def _pick(
    scored: list[_Scored],
    hint: str | None,
    allow_unlabeled: bool,
    prefer=None,
) -> str | None:
    """
    Выбор: сначала помеченные метками кандидаты (раньше в документе — лучше,
    т.к. реквизиты организации обычно идут до реквизитов банка),
    без меток — только если значение единственное.
    prefer(value) -> bool — дополнительный признак (например, ключ счёта сходится с БИК).
    """
    if not scored:
        return None

    labeled = [s for s in scored if s.labeled]
    pool = labeled
    if not pool:
        if not allow_unlabeled:
            return None
        values = {s.value for s in scored}
        if len(values) != 1 and not (prefer or hint):
            return None
        pool = scored

    def rank(s: _Scored):
        return (
            0 if prefer and prefer(s.value) else 1,
            0 if hint and s.value == hint else 1,
            s.position,
        )

    best = min(pool, key=rank)
    if not labeled and len({s.value for s in pool}) > 1:
        # Несколько разных чисел без меток: берём только если признак однозначно выделил одно
        top = [s for s in pool if rank(s)[:2] == rank(best)[:2]]
        if len({s.value for s in top}) > 1:
            return None
    return best.value


def _digits(value) -> str | None:
    if value is None:
        return None
    d = re.sub(r"\D", "", str(value))
    return d or None


def select_requisite_numbers(
    text: str, hints: dict | None = None
) -> dict[str, str | None]:
    """
    Возвращает {поле: значение | None} для числовых реквизитов.
    hints — значения, найденные LLM/regex; используются только для выбора среди равных.
    """
    hints = hints or {}
    fixed = _fix_ocr_digits(text)
    candidates = find_digit_candidates(text)
    labels = _find_labels(text)
    per_field = {f: _field_candidates(f, candidates, labels, fixed) for f in NUMERIC_FIELDS}
    hint = {f: _digits(hints.get(f)) for f in NUMERIC_FIELDS}

    result: dict[str, str | None] = {}
    result["inn"] = _pick(per_field["inn"], hint["inn"], allow_unlabeled=True)
    result["ogrn"] = _pick(per_field["ogrn"], hint["ogrn"], allow_unlabeled=True)

    inn = result["inn"]
    kpp_candidates = [s for s in per_field["kpp"] if not (inn and inn.startswith(s.value))]
    result["kpp"] = _pick(
        kpp_candidates,
        hint["kpp"],
        allow_unlabeled=False,
        prefer=(lambda v: inn is not None and len(inn) == 10 and v[:4] == inn[:4]),
    )

    bik_pool = per_field["bik"]
    ks_pool = per_field["correspondent_account"]
    rs_pool = per_field["checking_account"]

    # БИК подтверждается, если к нему есть подходящий по ключу корр./расч. счёт
    def bik_confirmed(v: str) -> bool:
        return any(validate_account_key(v, s.value, "correspondent") for s in ks_pool) or any(
            validate_account_key(v, s.value, "checking") for s in rs_pool
        )

    bik = _pick(bik_pool, hint["bik"], allow_unlabeled=True, prefer=bik_confirmed)
    result["bik"] = bik

    result["correspondent_account"] = _pick(
        ks_pool,
        hint["correspondent_account"],
        allow_unlabeled=True,
        prefer=(lambda v: bool(bik) and validate_account_key(bik, v, "correspondent") is True),
    )
    result["checking_account"] = _pick(
        rs_pool,
        hint["checking_account"],
        allow_unlabeled=True,
        prefer=(lambda v: bool(bik) and validate_account_key(bik, v, "checking") is True),
    )
    return result


def apply_number_candidates(
    data: dict, text: str, extracted_by: dict[str, str]
) -> tuple[dict, dict[str, str]]:
    """
    Подменяет числовые поля значениями, выбранными по кандидатам.
    Если кандидат не найден — оставляем то, что дали LLM/regex (валидация решит дальше).
    """
    selected = select_requisite_numbers(text, hints=data)
    merged = dict(data)
    sources = dict(extracted_by)
    for field, value in selected.items():
        if value is None:
            continue
        if _digits(merged.get(field)) != value:
            merged[field] = value
            sources[field] = "checksum"
        elif not sources.get(field):
            sources[field] = "checksum"
    return merged, sources
