from app.schemas.requisites import RequisitesData
from app.schemas.validation import ValidationReport
from app.validators.account_validator import validate_account, validate_cross_bik_corr
from app.validators.bik_validator import validate_bik
from app.validators.inn_validator import validate_inn
from app.validators.kpp_validator import validate_kpp
from app.validators.ogrn_validator import validate_ogrn


def validate_requisites(data: RequisitesData) -> tuple[ValidationReport, bool]:
    """
    Возвращает (ValidationReport, needs_review).

    needs_review = True если:
    - хотя бы одно критичное поле невалидно;
    - или отсутствуют важные реквизиты, которые обычно должны быть в карточке контрагента.
    """
    report = ValidationReport()
    errors: list[str] = []
    cross_checks: list[str] = []

    # --- Форматные проверки ---
    report.inn = validate_inn(data.inn)
    report.kpp = validate_kpp(data.kpp)
    report.ogrn = validate_ogrn(data.ogrn)
    report.bik = validate_bik(data.bik)
    report.checking_account = validate_account(data.checking_account, "checking")
    report.correspondent_account = validate_account(data.correspondent_account, "correspondent")

    # --- Кросс-проверка БИК ↔ корр. счёт ---
    cross_err = validate_cross_bik_corr(data.bik, data.correspondent_account)
    if cross_err:
        cross_checks.append(cross_err)
        errors.append(cross_err)

    # --- Сбор ошибок из форматных проверок ---
    critical_fields = [
        report.inn,
        report.kpp,
        report.ogrn,
        report.bik,
        report.checking_account,
        report.correspondent_account,
    ]

    for fv in critical_fields:
        if fv and not fv.valid and fv.reason:
            errors.append(fv.reason)

    # --- Проверка отсутствующих важных полей ---
    missing_critical: list[str] = []

    if not data.inn:
        missing_critical.append("ИНН отсутствует")
    if not data.kpp:
        missing_critical.append("КПП отсутствует")
    if not data.ogrn:
        missing_critical.append("ОГРН отсутствует")
    if not data.bik:
        missing_critical.append("БИК отсутствует")
    if not data.checking_account:
        missing_critical.append("Расчетный счет отсутствует")
    if not data.correspondent_account:
        missing_critical.append("Корреспондентский счет отсутствует")

    errors.extend(missing_critical)

    report.errors = list(dict.fromkeys(errors))
    report.cross_checks = cross_checks

    needs_review = len(report.errors) > 0
    return report, needs_review
