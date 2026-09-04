import re
from typing import Any

from loguru import logger

EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
    re.IGNORECASE,
)

PHONE_RE = re.compile(r"(?:\+7|8)[\s(.-]*\d[\d\s().-]{8,}\d")

INN_KPP_INLINE_RE = re.compile(
    r"(?:ИНН\s*/\s*КПП|ИНН/КПП|ИНН\s+КПП|ИННКПП)[^\d]{0,20}(\d{10}|\d{12})[^\d]{0,20}(\d{9})",
    re.IGNORECASE,
)

INN_KEY_RE = re.compile(
    r"(?:\bИНН\b|ИHH|ИНH|ИHН)[^\d]{0,20}(\d{10}|\d{12})",
    re.IGNORECASE,
)

KPP_KEY_RE = re.compile(
    r"(?:\bКПП\b|КПП:|КПП\s|[Кк]од\s+причины\s+постановки\s+на\s+уч[её]т)[^\d]{0,20}(\d{9})",
    re.IGNORECASE,
)

OGRN_KEY_RE = re.compile(
    r"(?:\bОГРН\b|ОГPH|ОГРH|OГPH)[^\d]{0,20}(\d{13})",
    re.IGNORECASE,
)

BIK_KEY_RE = re.compile(
    r"(?:\bБИК\s+банка\b|\bКод\s+БИК\b|\bБИК\b)[^\d]{0,20}([\d\s]{9,20})",
    re.IGNORECASE,
)

RS_KEY_RE = re.compile(
    r"(?:\d+[\.\)]\s*)?(?:Р/с|Р\\с|р/с|расч[её]тн(?:ый|ого)?\s+сч[её]т)[^\d]{0,20}([\d\s]{20,40})",
    re.IGNORECASE,
)

KS_KEY_RE = re.compile(
    r"(?:\d+[\.\)]\s*)?(?:К/с|К\\с|к/с|корр\.\s*сч[её]т|корреспондентск(?:ий|ого)?\s+сч[её]т)[^\d]{0,20}([\d\s]{20,40})",
    re.IGNORECASE,
)

BANK_LINE_RE = re.compile(
    r"(?:банк|банке)[:\s]+(.{5,120})",
    re.IGNORECASE,
)

# Хвост подписи поля: необязательное уточнение в скобках плюс разделитель —
# либо перевод строки, если значение стоит следующей строкой. Ключевое отличие
# от прежнего `[^\n]{0,30}`: сюда не может попасть начало значения, потому что
# разделитель обязателен, когда метка и значение стоят в одной строке. Раньше
# жадный квантификатор съедал тридцать символов самого значения.
_LABEL_TAIL = r"(?:\s*\([^)\n]{0,40}\))?[ \t]*(?:[:|—–\-]+[ \t]*|\n[ \t]*)"

COMPANY_FULL_RE = re.compile(
    r"(?:Полное\s+наименование(?:\s+организации)?|наименование\s+контрагента)"
    + _LABEL_TAIL
    + r"(.{10,200})",
    re.IGNORECASE,
)

SHORT_NAME_RE = re.compile(
    r"(?:Краткое|Сокращ[её]нное)\s+наименование(?:\s+организации)?"
    + _LABEL_TAIL
    + r"(.{3,150})",
    re.IGNORECASE,
)

LEGAL_ADDRESS_RE = re.compile(
    r"(?:Юридический\s+адрес)" + _LABEL_TAIL + r"(.{10,250})",
    re.IGNORECASE,
)

POSTAL_ADDRESS_RE = re.compile(
    r"(?:Почтовый\s+адрес)" + _LABEL_TAIL + r"(.{10,250})",
    re.IGNORECASE,
)

# Подпись поля перед названием банка — только на самом старте строки:
# `_extract_bank_name()` уже отобрал строку по признаку «упоминает банк», это
# просто снимает подпись, если она там есть. Без якоря `^` риск нет — строка
# на входе всегда одна, а не весь текст.
BANK_LABEL_RE = re.compile(
    r"^(?:наименование\s+(?:полное\s+)?(?:учреждения\s+)?банка|"
    r"банковские\s+реквизиты|банк)" + _LABEL_TAIL,
    re.IGNORECASE,
)

CEO_ROW_RE = re.compile(
    r"(Генеральный\s+директор|Директор|Исполнительный\s+директор|Президент|Руководитель|ИП)"
    r"[^|\n]{0,80}[|\t]\s*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})",
    re.IGNORECASE,
)

CEO_SIGN_RE = re.compile(
    r"(Генеральный\s+директор|Директор|Исполнительный\s+директор|Президент|Руководитель|ИП)\s+"
    r"([А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\.)",
    re.IGNORECASE,
)

CEO_FULL_NAME_RE = re.compile(
    r"(Генеральный\s+директор|Директор|Исполнительный\s+директор|Президент|Руководитель)"
    r"[,:\s]+([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)",
    re.IGNORECASE,
)

_PATRONYMIC_SUFFIXES = ("ич", "на", "вна", "евна", "овна", "евич", "ович")

# Символы, которыми в документах отделяют подпись поля от значения. Вертикальная
# черта и табуляция сюда входят обязательно: в распознанных таблицах строка
# выглядит как «Директор | Иванов И.И.», и без них разделитель уезжал в значение.
_LABEL_SEPARATORS = " :;-—–|\t"


def _starts_with_label(lowered: str, label: str) -> bool:
    """
    `startswith`, но с проверкой границы слова.

    Без неё `label="банк"` совпадал бы и внутри «банковские реквизиты» —
    слово начинается с тех же букв, но это не подпись поля. Сразу после
    подписи должен идти разделитель или конец строки, иначе значение
    нарежется с середины слова. Найдено на реальном документе при замере
    accuracy (Э16): «Банковские реквизиты | ...» превращалось в bank_name
    «овские реквизиты | ...».
    """
    if not lowered.startswith(label):
        return False
    return len(lowered) == len(label) or lowered[len(label)] in _LABEL_SEPARATORS


def _make_short_fio(full_fio: str) -> str | None:
    parts = full_fio.strip().split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    if len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."
    return None


def _is_patronymic(word: str) -> bool:
    """Проверяет, является ли слово отчеством по суффиксу."""
    return any(word.endswith(s) for s in _PATRONYMIC_SUFFIXES)


def _normalize_fio_order(parts: list[str]) -> str:
    """
    Приводит ФИО к порядку: Фамилия Имя Отчество.
    Отчество определяется по суффиксу.
    """
    if len(parts) != 3:
        return " ".join(parts)

    patronymic_idx = next((i for i, p in enumerate(parts) if _is_patronymic(p)), None)

    if patronymic_idx is None:
        return " ".join(parts)

    if patronymic_idx == 2:
        # Уже Фамилия Имя Отчество
        return " ".join(parts)

    if patronymic_idx == 1:
        # Порядок Имя Отчество Фамилия → переставляем
        return f"{parts[2]} {parts[0]} {parts[1]}"

    # Нестандартный порядок — не трогаем
    return " ".join(parts)


def _extract_ceo(text: str) -> tuple[str | None, str | None, str | None]:
    match = CEO_ROW_RE.search(text)
    if match:
        position = match.group(1).strip()
        fio_raw = match.group(2).strip()
        parts = fio_raw.split()
        fio_full = _normalize_fio_order(parts) if len(parts) == 3 else fio_raw
        fio_short = _make_short_fio(fio_full)
        return position, fio_full, fio_short

    match = CEO_FULL_NAME_RE.search(text)
    if match:
        position = match.group(1).strip()
        fio_full = match.group(2).strip()
        fio_short = _make_short_fio(fio_full)
        return position, fio_full, fio_short

    match = CEO_SIGN_RE.search(text)
    if match:
        position = match.group(1).strip()
        fio_short = match.group(2).strip()
        parts = fio_short.split()
        # Формат «И.О. Фамилия» → «Фамилия И.О.»
        if len(parts) == 2 and re.match(r"[А-ЯЁ]\.[А-ЯЁ]\.", parts[0]):
            fio_short = f"{parts[1]} {parts[0]}"
        return position, None, fio_short

    return None, None, None


def _digits_only(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


def _clean_spaces(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip()


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits[0] in ("7", "8"):
        return "+7" + digits[1:]
    return digits


def _find_first(pattern: re.Pattern, text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    if match.groups():
        return match.group(1).strip()
    return match.group(0).strip()


def _find_all_digit_sequences(text: str, min_len: int, max_len: int) -> list[str]:
    matches = re.findall(rf"\d{{{min_len},{max_len}}}", text)
    result: list[str] = []
    for item in matches:
        if item not in result:
            result.append(item)
    return result


def _extract_company_name(text: str) -> str | None:
    match = COMPANY_FULL_RE.search(text)
    if not match:
        return None
    value = _clean_spaces(match.group(1))
    if value and len(value) >= 5:
        return value
    return None


def _extract_short_name(text: str) -> str | None:
    match = SHORT_NAME_RE.search(text)
    if not match:
        return None
    value = _clean_spaces(match.group(1))
    if value and len(value) >= 3:
        return value
    return None


def _extract_legal_address(text: str) -> str | None:
    match = LEGAL_ADDRESS_RE.search(text)
    if not match:
        return None
    value = _clean_spaces(match.group(1))
    return value or None


def _extract_postal_address(text: str) -> str | None:
    for line in text.splitlines():
        line = _clean_spaces(line)
        if not line:
            continue
        lowered = line.lower()
        if "почтовый адрес" in lowered:
            # `[:\s]*` снимал только пробел и двоеточие после подписи, но не
            # «|» — разделитель соседних ячеек PDF-таблицы (Э13). В значении
            # оставался осиротевший «|» в начале. Найдено на реальном
            # документе при замере accuracy (Э16).
            value = re.sub(r"(?i)^.*почтовый\s+адрес", "", line).strip(
                _LABEL_SEPARATORS + ","
            )
            return value or None
        if "отделение почтовой связи" in lowered:
            value = re.sub(r"(?i)^.*отделение\s+почтовой\s+связи", "", line).strip(
                _LABEL_SEPARATORS + ","
            )
            return value or line

    match = POSTAL_ADDRESS_RE.search(text)
    if match:
        value = _clean_spaces(match.group(1))
        return value or None

    return None


def _extract_email(text: str) -> str | None:
    normalized_text = text.replace("E mail", "E-mail").replace("E-mail;", "E-mail:")
    for line in normalized_text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = EMAIL_RE.search(line.replace(" ", ""))
        if match:
            return match.group(0)
    return None


def _extract_phones(text: str) -> list[str]:
    found = PHONE_RE.findall(text)
    result: list[str] = []
    for item in found:
        normalized = _normalize_phone(item)
        digits = re.sub(r"\D", "", normalized)
        if len(digits) != 11:
            continue
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _extract_inn_kpp(text: str) -> tuple[str | None, str | None]:
    inn: str | None = None
    kpp: str | None = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        lowered = line.lower()

        if "инн" in lowered and inn is None:
            # Сначала ищем 12-значный, потом 10-значный
            match = re.search(r"\b(\d{12}|\d{10})\b", line, re.IGNORECASE)
            if match:
                inn = match.group(1)

        if "кпп" in lowered and kpp is None:
            match = re.search(r"\b(\d{9})\b", line, re.IGNORECASE)
            if match:
                candidate = match.group(1)
                # Не берём КПП если он является префиксом ИНН
                if inn and inn.startswith(candidate):
                    continue
                kpp = candidate

    return inn, kpp


def _extract_ogrn(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "огрн" in line.lower():
            match = re.search(r"\b(\d{13})\b", line, re.IGNORECASE)
            if match:
                return match.group(1)
    return None


def _extract_bik(text: str) -> str | None:
    raw = _find_first(BIK_KEY_RE, text)
    if raw:
        digits = _digits_only(raw)
        if digits and len(digits) >= 9:
            candidate = digits[:9]
            if candidate.startswith("04"):
                return candidate

    # Fallback по всему тексту
    for candidate in _find_all_digit_sequences(text, 9, 9):
        if candidate.startswith("04"):
            return candidate

    return None


def _extract_rs(text: str) -> str | None:
    raw = _find_first(RS_KEY_RE, text)
    if raw:
        digits = _digits_only(raw)
        if digits and len(digits) >= 20:
            candidate = digits[:20]
            if candidate.startswith("40"):
                return candidate

    # Fallback по всему тексту
    for candidate in _find_all_digit_sequences(text, 20, 20):
        if candidate.startswith("40"):
            return candidate

    return None


def _extract_ks(text: str) -> str | None:
    raw = _find_first(KS_KEY_RE, text)
    if raw:
        digits = _digits_only(raw)
        if digits and len(digits) >= 20:
            candidate = digits[:20]
            if candidate.startswith("30"):
                return candidate

    # Fallback по всему тексту
    for candidate in _find_all_digit_sequences(text, 20, 20):
        if candidate.startswith("30"):
            return candidate

    return None


def _extract_bank_name(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        lowered = line.lower()
        if (
            "банк" in lowered
            and "бик" not in lowered
            and "счет" not in lowered
            and "счёт" not in lowered
        ):
            cleaned = _clean_spaces(line)
            if cleaned and len(cleaned) >= 5:
                # Строка вида «Банковские реквизиты | ПАО Сбербанк» —
                # склеенные через " | " ячейки таблицы (Э13). Отрезаем
                # распознанную подпись поля, если она есть; если нет —
                # строка и так была просто названием банка без подписи.
                value = BANK_LABEL_RE.sub("", cleaned, count=1).strip()
                return value if len(value) >= 5 else cleaned

    match = BANK_LINE_RE.search(text)
    if match:
        value = _clean_spaces(match.group(1))
        if value:
            value = re.split(
                r"(?:\bБИК\b|\bр/с\b|\bк/с\b|\bИНН\b|\bКПП\b)",
                value,
                flags=re.IGNORECASE,
            )[0].strip(" ,;:")
            return value or None

    return None


def _extract_from_partner_card(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}

    lines = [_clean_spaces(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    text_fields = {
        "полное наименование организации": "company_name",
        "краткое наименование организации": "short_name",
        "юридический адрес": "legal_address",
        "почтовый адрес": "postal_address",
        "банк": "bank_name",
        "директор": "ceo_fio_full",
    }

    strict_inline_fields = {
        "инн": ("inn", r"(\d{10}|\d{12})"),
        "кпп": ("kpp", r"(\d{9})"),
        "огрн": ("ogrn", r"(\d{13})"),
        "бик": ("bik", r"(\d{9})"),
        "корр. счет": ("correspondent_account", r"(\d{20})"),
        "корр счет": ("correspondent_account", r"(\d{20})"),
        "корреспондентский счет": ("correspondent_account", r"(\d{20})"),
        "расчетный счет": ("checking_account", r"(\d{20})"),
        "расчётный счёт": ("checking_account", r"(\d{20})"),
        "телефон": ("phone", r"((?:\+7|8)[\d\s().-]{10,})"),
        "e-mail": ("email", r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})"),
        "email": ("email", r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})"),
    }

    for idx, line in enumerate(lines):
        lowered = line.lower().strip()

        # Сначала проверяем строгие инлайн-поля
        matched_inline = False
        for label, (field, pattern) in strict_inline_fields.items():
            if _starts_with_label(lowered, label):
                match = re.search(pattern, line, flags=re.IGNORECASE)
                if match:
                    result[field] = match.group(1).strip()
                matched_inline = True
                break

        if matched_inline:
            continue  # текстовые поля для этой строки не проверяем

        # Затем текстовые поля
        for label, field in text_fields.items():
            if _starts_with_label(lowered, label):
                tail = line[len(label) :].strip(_LABEL_SEPARATORS)
                value = (
                    tail if tail else (lines[idx + 1] if idx + 1 < len(lines) else None)
                )
                if value:
                    result[field] = value.strip()
                break

    # Постобработка
    for field in (
        "company_name",
        "short_name",
        "legal_address",
        "postal_address",
        "bank_name",
    ):
        if result.get(field):
            result[field] = _clean_spaces(result[field])

    if result.get("phone"):
        phones = _extract_phones(result["phone"])
        result["phone"] = ", ".join(phones) if phones else None

    if result.get("email"):
        result["email"] = _extract_email(result["email"])

    for field in (
        "inn",
        "kpp",
        "ogrn",
        "bik",
        "checking_account",
        "correspondent_account",
    ):
        if result.get(field):
            result[field] = _digits_only(result[field])

    if result.get("ceo_fio_full"):
        fio_full = re.sub(
            r"\s+Действует\s+на\s+основании\s+Устава.*$",
            "",
            result["ceo_fio_full"],
            flags=re.IGNORECASE,
        ).strip()

        # Порядок слов приводим здесь же. Раньше этого не делалось, и результат
        # карточки перекрывал корректно переставленное ФИО из _extract_ceo():
        # «Иван Иванович Петров» так и уходил в документ.
        parts = fio_full.split()
        if len(parts) == 3:
            fio_full = _normalize_fio_order(parts)

        result["ceo_fio_full"] = fio_full

        # Не перезаписываем позицию если уже установлена
        result.setdefault("ceo_position", "Директор")

        # Краткую форму пересобираем всегда: если порядок изменился, ранее
        # найденная краткая форма относится к другой фамилии.
        result["ceo_fio"] = _make_short_fio(fio_full) or result.get("ceo_fio")

    return result


def extract_fallback_fields(text: str) -> dict[str, Any]:
    partner_card_data = _extract_from_partner_card(text)
    inn, kpp = _extract_inn_kpp(text)
    ogrn = _extract_ogrn(text)
    bik = _extract_bik(text)
    checking_account = _extract_rs(text)
    correspondent_account = _extract_ks(text)

    # Только имена найденных полей, без значений. Прежние строки печатали
    # четыре тысячи символов документа и все реквизиты целиком; пока модуль
    # писал в неподключённый stdlib-логгер, это никуда не уходило, но после
    # перехода на loguru попало бы прямиком в logs/app.log (CLAUDE.md).
    logger.debug(
        "fallback scan",
        chars=len(text),
        card_fields=sorted(k for k, v in partner_card_data.items() if v),
        found=sorted(
            name
            for name, value in (
                ("inn", inn),
                ("kpp", kpp),
                ("ogrn", ogrn),
                ("bik", bik),
                ("checking_account", checking_account),
                ("correspondent_account", correspondent_account),
            )
            if value
        ),
    )

    if inn:
        inn_digits = re.sub(r"\D", "", inn)
        if len(inn_digits) not in (10, 12):
            inn = None

    if kpp:
        kpp_digits = re.sub(r"\D", "", kpp)
        if len(kpp_digits) != 9:
            kpp = None

    if ogrn:
        ogrn_digits = re.sub(r"\D", "", ogrn)
        if len(ogrn_digits) != 13:
            ogrn = None

    phones = _extract_phones(text)
    phone_value = ", ".join(phones) if phones else None

    ceo_position, ceo_fio_full, ceo_fio = _extract_ceo(text)

    result = {
        "company_name": partner_card_data.get("company_name")
        or _extract_company_name(text),
        "short_name": partner_card_data.get("short_name") or _extract_short_name(text),
        "legal_address": partner_card_data.get("legal_address")
        or _extract_legal_address(text),
        "postal_address": partner_card_data.get("postal_address")
        or _extract_postal_address(text),
        "inn": partner_card_data.get("inn") or inn,
        "kpp": partner_card_data.get("kpp") or kpp,
        "ogrn": partner_card_data.get("ogrn") or ogrn,
        "bik": partner_card_data.get("bik") or bik,
        "checking_account": partner_card_data.get("checking_account")
        or checking_account,
        "correspondent_account": partner_card_data.get("correspondent_account")
        or correspondent_account,
        "bank_name": partner_card_data.get("bank_name") or _extract_bank_name(text),
        "email": partner_card_data.get("email") or _extract_email(text),
        "phone": partner_card_data.get("phone") or phone_value,
        "ceo_position": partner_card_data.get("ceo_position") or ceo_position,
        "ceo_fio_full": partner_card_data.get("ceo_fio_full") or ceo_fio_full,
        "ceo_fio": partner_card_data.get("ceo_fio") or ceo_fio,
    }

    logger.debug("fallback result", fields=sorted(k for k, v in result.items() if v))
    return result


def _is_empty(value: Any) -> bool:
    return value is None or value == ""


# Метки чужих полей. Если они оказались внутри наименования или адреса — это
# не значение, а склейка двух строк документа в одну.
_FOREIGN_LABEL_RE = re.compile(
    r"\b(ИНН|КПП|ОГРН|ОГРНИП|БИК|Р/с|К/с|расч[её]тн|корреспондентск"
    r"|телефон|e-?mail|директор)\b|сч[её]т",
    re.IGNORECASE,
)

# Организационно-правовая форма — признак того, что в значении действительно
# наименование организации, а не обрывок соседней строки.
_OPF_RE = re.compile(
    r"(\bООО\b|\bОАО\b|\bЗАО\b|\bПАО\b|\bАО\b|\bНАО\b|\bИП\b|\bАНО\b"
    r"|\bГУП\b|\bМУП\b|Обществ\w*\s+с\s+ограниченной|Акционерн\w*\s+обществ\w*"
    r"|Индивидуальн\w*\s+предпринимател\w*)",
    re.IGNORECASE,
)


def _looks_contaminated(value: str) -> bool:
    """Внутри значения метка чужого поля или длинное число — признак склейки."""
    return bool(_FOREIGN_LABEL_RE.search(value)) or bool(re.search(r"\d{9,}", value))


def _is_better_regex_value(field: str, llm_value: Any, regex_value: Any) -> bool:
    if _is_empty(regex_value):
        return False

    if _is_empty(llm_value):
        return True

    llm_str = str(llm_value).strip()
    regex_str = str(regex_value).strip()

    llm_digits = _digits_only(llm_str)
    regex_digits = _digits_only(regex_str)

    if field == "company_name":
        # Прежнее правило «длиннее — значит лучше» работало обратно
        # задуманному: чем больше регекс перехватил соседних строк, тем
        # увереннее он побеждал корректное значение LLM.
        if _looks_contaminated(regex_str):
            return False
        return bool(_OPF_RE.search(regex_str)) and not _OPF_RE.search(llm_str)

    if field == "short_name":
        if _looks_contaminated(regex_str):
            return False
        return len(regex_str) <= len(llm_str) and bool(_OPF_RE.search(regex_str))

    if field == "legal_address":
        if _looks_contaminated(regex_str):
            return False
        return len(regex_str) > len(llm_str)

    if field == "postal_address":
        if _looks_contaminated(regex_str):
            return False
        return len(regex_str) > len(llm_str) or regex_str != llm_str

    if field == "email":
        return "@" in regex_str and "@" not in llm_str

    if field == "phone":
        if not llm_digits or not regex_digits:
            return bool(regex_digits) and len(regex_digits) == 11
        return len(regex_digits) == 11 and len(llm_digits) != 11

    if field == "inn":
        if llm_digits and regex_digits:
            if len(regex_digits) in (10, 12) and len(llm_digits) not in (10, 12):
                return True
            if len(regex_digits) in (10, 12) and len(llm_digits) == 20:
                return True

    if field == "kpp":
        if llm_digits and regex_digits:
            if len(regex_digits) == 9 and len(llm_digits) != 9:
                return True

    if field == "ogrn":
        if llm_digits and regex_digits:
            if len(regex_digits) == 13 and len(llm_digits) != 13:
                return True

    if field == "bik":
        if llm_digits and regex_digits:
            if (
                len(regex_digits) == 9
                and regex_digits.startswith("04")
                and (len(llm_digits) != 9 or not llm_digits.startswith("04"))
            ):
                return True

    if field == "checking_account":
        if llm_digits and regex_digits:
            if (len(llm_digits) != 20 or not llm_digits.startswith("40")) and (
                len(regex_digits) == 20 and regex_digits.startswith("40")
            ):
                return True

    if field == "correspondent_account":
        if llm_digits and regex_digits:
            if (len(llm_digits) != 20 or not llm_digits.startswith("30")) and (
                len(regex_digits) == 20 and regex_digits.startswith("30")
            ):
                return True

    return False


def merge_llm_and_fallback(
    llm_data: dict[str, Any],
    fallback_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    logger.debug(
        "merge start",
        llm_fields=sorted(k for k, v in llm_data.items() if not _is_empty(v)),
        regex_fields=sorted(k for k, v in fallback_data.items() if not _is_empty(v)),
    )

    merged = dict(llm_data)
    extracted_by: dict[str, str] = {}

    for key in merged:
        if not _is_empty(merged.get(key)):
            extracted_by[key] = "llm"

    for key, fallback_value in fallback_data.items():
        llm_value = merged.get(key)

        if _is_empty(llm_value) and not _is_empty(fallback_value):
            merged[key] = fallback_value
            extracted_by[key] = "regex"
            continue

        if _is_better_regex_value(key, llm_value, fallback_value):
            merged[key] = fallback_value
            extracted_by[key] = "regex"

    # `_normalize_phone()` до сих пор применялась только внутри regex-слоя
    # (`_extract_phones`). Когда телефон побеждал от LLM, в результате
    # оставалось исходное форматирование документа — промпт не просит
    # нормализовать телефон, в отличие от ИНН/КПП/счетов. Функция
    # идемпотентна на уже нормализованном значении, поэтому применяем её
    # здесь один раз, независимо от источника.
    if not _is_empty(merged.get("phone")):
        merged["phone"] = _normalize_phone(merged["phone"])

    logger.debug("merge done", extracted_by=extracted_by)

    return merged, extracted_by
