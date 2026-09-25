"""
Кросс-полевые проверки.

Все функции здесь возвращают `str | None` — текст предупреждения или `None`.
Они ничего не мутируют и никогда не создают жёсткую ошибку: это дополнительные
источники warning для `validate_requisites()`, а не самостоятельные валидаторы
полей.

Общий принцип: если хотя бы одно из участвующих полей отсутствует или не прошло
собственную проверку, кросс-проверка молчит. Её ошибка уже показана рядом с
этим полем, дублировать её шумом здесь незачем.
"""

from app.schemas.validation import FieldValidation
from app.validators.account_validator import account_control_key_ok
from app.validators.inn_validator import validate_inn
from app.validators.kpp_validator import validate_kpp

_ACCOUNT_LABELS = {
    "checking": "расчётного счёта",
    "correspondent": "корреспондентского счёта",
}


def validate_bik_account_consistency(
    bik_result: FieldValidation | None,
    account_result: FieldValidation | None,
    account_type: str,
) -> str | None:
    """
    Контрольный ключ БИК ↔ счёт по методике ЦБ РФ № 515.

    Результат — всегда только предупреждение, никогда не блокирующая ошибка
    (CLAUDE.md). Проверка пропускается, если БИК или счёт отсутствует либо не
    прошёл собственную форматную проверку: считать ключ по заведомо битым
    данным бессмысленно.
    """
    if not _is_usable(bik_result) or not _is_usable(account_result):
        return None

    bik = bik_result.normalized_value
    account = account_result.normalized_value
    if not bik or not account:
        return None

    if account_control_key_ok(bik, account, account_type):
        return None

    label = _ACCOUNT_LABELS.get(account_type, "счёта")
    return (
        f"контрольный ключ {label} не совпадает с БИК "
        f"(методика ЦБ РФ № 515) — проверьте пару БИК/счёт"
    )


def validate_inn_kpp_consistency(inn: str | None, kpp: str | None) -> str | None:
    """
    У индивидуального предпринимателя КПП не бывает: 12-значный ИНН вместе с
    заполненным КПП — признак того, что поля перепутаны или скопированы из
    чужой карточки.

    Предупреждение выдаётся, только если ИНН действительно валиден и
    12-значный, а КПП валиден по структуре. Если КПП сам по себе невалиден, его
    ошибка уже видна отдельно.
    """
    if inn is None or kpp is None:
        return None

    inn_result = validate_inn(inn)
    if not inn_result.valid or len(inn_result.normalized_value or "") != 12:
        return None

    if not validate_kpp(kpp).valid:
        return None

    return (
        "12-значный ИНН принадлежит индивидуальному предпринимателю, "
        "а у ИП не бывает КПП — проверьте пару ИНН/КПП"
    )


def validate_ceo_fio_consistency(
    ceo_fio_full: str | None, ceo_fio: str | None
) -> str | None:
    """
    Фамилия в полном и кратком ФИО руководителя должна совпадать.

    Сравнивается только первое слово: краткая форма — это «Фамилия И.О.», и
    инициалы сопоставлять смысла нет. Регистр и лишние пробелы игнорируются.
    """
    if not ceo_fio_full or not ceo_fio:
        return None

    full_surname = _first_word(ceo_fio_full)
    short_surname = _first_word(ceo_fio)
    if not full_surname or not short_surname:
        return None

    if full_surname.casefold() == short_surname.casefold():
        return None

    return (
        f"фамилия в полном ФИО («{full_surname}») не совпадает с фамилией "
        f"в кратком («{short_surname}»)"
    )


def _is_usable(result: FieldValidation | None) -> bool:
    """Поле пригодно для кросс-проверки: заполнено и прошло свою проверку."""
    return bool(result and result.valid and not result.is_missing)


def _first_word(value: str) -> str:
    parts = value.split()
    return parts[0] if parts else ""
