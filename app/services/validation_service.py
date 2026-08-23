"""
Оркестратор валидации: прогоняет все 16 полей через их валидаторы, добавляет
кросс-полевые проверки и собирает итоговый отчёт.

Разделение потоков задано в CLAUDE.md и соблюдается здесь буквально:

- жёсткая ошибка (`reason`) → `errors`, блокирует генерацию без подтверждения;
- предупреждение (`warning`) → `warnings`, не блокирует никогда;
- незаполненное поле → `is_missing`. Ошибкой это считается только для шести
  обязательных числовых реквизитов; отсутствие остальных полей нормально.

Побочный эффект: поля, не прошедшие проверку, обнуляются в `data`, чтобы
заведомо неверное значение не попало в шаблон. Исходное значение при этом не
теряется — оно остаётся в `FieldValidation.raw_value` и именно оттуда
показывается в review-форме.
"""

from app.schemas.requisites import RequisitesData
from app.schemas.validation import FieldValidation, ValidationReport
from app.validators.account_validator import validate_account, validate_cross_bik_corr
from app.validators.address_validator import validate_address
from app.validators.bank_name_validator import validate_bank_name
from app.validators.bik_validator import validate_bik
from app.validators.ceo_validator import (
    validate_ceo_fio_full,
    validate_ceo_fio_short,
    validate_ceo_position,
)
from app.validators.company_name_validator import validate_company_name
from app.validators.cross_field_validator import (
    validate_bik_account_consistency,
    validate_ceo_fio_consistency,
    validate_inn_kpp_consistency,
)
from app.validators.email_validator import validate_email
from app.validators.inn_validator import validate_inn
from app.validators.kpp_validator import validate_kpp
from app.validators.ogrn_validator import validate_ogrn
from app.validators.phone_validator import validate_phone
from app.validators.short_name_validator import validate_short_name

_FIELD_LABELS = {
    "company_name": "Полное наименование",
    "short_name": "Сокращённое наименование",
    "legal_address": "Юридический адрес",
    "postal_address": "Почтовый адрес",
    "ogrn": "ОГРН",
    "inn": "ИНН",
    "kpp": "КПП",
    "bank_name": "Наименование банка",
    "checking_account": "Расчётный счёт",
    "correspondent_account": "Корреспондентский счёт",
    "bik": "БИК",
    "ceo_position": "Должность руководителя",
    "ceo_fio_full": "ФИО руководителя (полное)",
    "ceo_fio": "ФИО руководителя (краткое)",
    "phone": "Телефон",
    "email": "E-mail",
}

# Поля, отсутствие которых само по себе требует внимания: без них договор не
# заполнить. Для остальных `is_missing` — нормальное состояние.
_REQUIRED_FIELDS = (
    "inn",
    "kpp",
    "ogrn",
    "bik",
    "checking_account",
    "correspondent_account",
)


def validate_requisites(data: RequisitesData) -> tuple[ValidationReport, bool]:
    """
    Возвращает `(ValidationReport, needs_review)`.

    Побочный эффект: обнуляет в `data` поля, не прошедшие проверку.
    """
    report = ValidationReport()

    field_results = _run_field_validators(data)
    for name, result in field_results.items():
        setattr(report, name, result)

    errors: list[str] = []
    warnings: list[str] = []
    review_reasons: list[str] = []

    # ── Жёсткие ошибки: значение введено, но неверно ────────────────────────
    for name, result in field_results.items():
        if result.valid or result.is_missing:
            continue

        label = _FIELD_LABELS[name]
        reason = result.reason or "invalid format"
        errors.append(reason)
        review_reasons.append(
            f"{label}: значение {result.raw_value!r} отклонено — {reason}"
        )
        # Не пускаем заведомо неверное значение в шаблон. raw_value сохранён
        # в отчёте и показывается пользователю в форме.
        setattr(data, name, None)

    # ── Отсутствие обязательных полей ───────────────────────────────────────
    for name in _REQUIRED_FIELDS:
        if field_results[name].is_missing:
            message = f"{_FIELD_LABELS[name]} отсутствует"
            errors.append(message)
            review_reasons.append(message)

    # ── Кросс-полевые проверки: только предупреждения ───────────────────────
    cross_checks = _run_cross_checks(data, field_results)
    warnings.extend(cross_checks)

    # ── Предупреждения самих полей ──────────────────────────────────────────
    for result in field_results.values():
        if result.warning:
            warnings.append(result.warning)

    report.errors = _dedupe(errors)
    report.warnings = _dedupe(warnings)
    report.review_reasons = _dedupe(review_reasons)
    report.cross_checks = _dedupe(cross_checks)

    needs_review = bool(report.errors) or bool(report.warnings)
    return report, needs_review


def _run_field_validators(data: RequisitesData) -> dict[str, FieldValidation]:
    return {
        "company_name": validate_company_name(data.company_name),
        "short_name": validate_short_name(data.short_name),
        "legal_address": validate_address(data.legal_address),
        "postal_address": validate_address(data.postal_address),
        "ogrn": validate_ogrn(data.ogrn),
        "inn": validate_inn(data.inn),
        "kpp": validate_kpp(data.kpp),
        "bank_name": validate_bank_name(data.bank_name),
        "checking_account": validate_account(data.checking_account, "checking"),
        "correspondent_account": validate_account(
            data.correspondent_account, "correspondent"
        ),
        "bik": validate_bik(data.bik),
        "ceo_position": validate_ceo_position(data.ceo_position),
        "ceo_fio_full": validate_ceo_fio_full(data.ceo_fio_full),
        "ceo_fio": validate_ceo_fio_short(data.ceo_fio),
        "phone": validate_phone(data.phone),
        "email": validate_email(data.email),
    }


def _run_cross_checks(
    data: RequisitesData, field_results: dict[str, FieldValidation]
) -> list[str]:
    """
    Кросс-полевые проверки. Все результаты — предупреждения: ни одна из них не
    блокирует генерацию документа (CLAUDE.md).

    Контрольный ключ дописывается в `warning` самого счёта, чтобы в форме он
    оказался рядом с полем, а не в общем списке внизу.
    """
    checks: list[str] = []

    bik_result = field_results["bik"]

    for account_field, account_type in (
        ("checking_account", "checking"),
        ("correspondent_account", "correspondent"),
    ):
        account_result = field_results[account_field]
        key_warning = validate_bik_account_consistency(
            bik_result, account_result, account_type
        )
        if key_warning:
            account_result.warning = _append_warning(
                account_result.warning, key_warning
            )

    structural = validate_cross_bik_corr(data.bik, data.correspondent_account)
    if structural:
        checks.append(structural)

    inn_kpp = validate_inn_kpp_consistency(data.inn, data.kpp)
    if inn_kpp:
        checks.append(inn_kpp)

    ceo_fio = validate_ceo_fio_consistency(data.ceo_fio_full, data.ceo_fio)
    if ceo_fio:
        checks.append(ceo_fio)

    return checks


def _append_warning(existing: str | None, addition: str) -> str:
    return f"{existing}; {addition}" if existing else addition


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
