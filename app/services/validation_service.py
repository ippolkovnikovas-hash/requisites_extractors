from app.schemas.requisites import RequisitesData
from app.schemas.validation import ValidationReport
from app.validators.account_validator import validate_account, validate_cross_bik_corr
from app.validators.bik_validator import validate_bik
from app.validators.inn_validator import validate_inn
from app.validators.kpp_validator import validate_kpp
from app.validators.ogrn_validator import validate_ogrn

_FIELD_LABELS = {
    "inn": "ИНН",
    "kpp": "КПП",
    "ogrn": "ОГРН",
    "bik": "БИК",
    "checking_account": "Расчётный счёт",
    "correspondent_account": "Корреспондентский счёт",
}


def validate_requisites(data: RequisitesData) -> tuple[ValidationReport, bool]:
    """
    Возвращает (ValidationReport, needs_review).
    Побочный эффект: обнуляет поля data, не прошедшие форматную проверку,
    чтобы они не попали в шаблон с заведомо неверным значением.
    """
    report = ValidationReport()
    errors: list[str] = []
    review_reasons: list[str] = []
    cross_checks: list[str] = []

    # --- Форматные проверки ---
    report.inn = validate_inn(data.inn)
    report.kpp = validate_kpp(data.kpp)
    report.ogrn = validate_ogrn(data.ogrn)
    report.bik = validate_bik(data.bik)
    report.checking_account = validate_account(data.checking_account, "checking")
    report.correspondent_account = validate_account(data.correspondent_account, "correspondent")

    # --- Очистка невалидных полей (не записываем мусор в шаблон) ---
    field_report_pairs = [
        ("inn", report.inn),
        ("kpp", report.kpp),
        ("ogrn", report.ogrn),
        ("bik", report.bik),
        ("checking_account", report.checking_account),
        ("correspondent_account", report.correspondent_account),
    ]
    for field_name, fv in field_report_pairs:
        if fv and not fv.valid:
            original = getattr(data, field_name)
            if original is not None:
                label = _FIELD_LABELS.get(field_name, field_name)
                reason = fv.reason or "invalid format"
                review_reasons.append(f"{label}: значение {original!r} отклонено — {reason}")
                errors.append(reason)
            setattr(data, field_name, None)

    # --- Кросс-проверка БИК ↔ корр. счёт ---
    cross_err = validate_cross_bik_corr(data.bik, data.correspondent_account)
    if cross_err:
        cross_checks.append(cross_err)
        errors.append(cross_err)
        review_reasons.append(f"Кросс-проверка: {cross_err}")

    # --- Проверка отсутствующих важных полей ---
    missing_labels = [
        label for field_name, label in _FIELD_LABELS.items()
        if not getattr(data, field_name)
    ]
    for label in missing_labels:
        msg = f"{label} отсутствует"
        errors.append(msg)
        review_reasons.append(msg)

    report.errors = list(dict.fromkeys(errors))
    report.review_reasons = list(dict.fromkeys(review_reasons))
    report.cross_checks = cross_checks

    needs_review = len(report.errors) > 0
    return report, needs_review
