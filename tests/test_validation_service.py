"""Тесты сервиса валидации реквизитов."""
import pytest
from app.schemas.requisites import RequisitesData
from app.services.validation_service import validate_requisites


def make_data(**kwargs) -> RequisitesData:
    defaults = dict(
        inn="7744012347",
        kpp="774401001",
        ogrn="1027700123450",
        bik="044525225",
        # Р/с синтетически подобран для согласования с БИК по контрольному ключу;
        # не является независимым тест-вектором и не используется для проверки алгоритма.
        checking_account="40702810200000012345",
        correspondent_account="30101810400000000225",
    )
    defaults.update(kwargs)
    return RequisitesData(**defaults)


def test_valid_requisites_no_review():
    report, needs_review = validate_requisites(make_data())
    assert not needs_review
    assert report.errors == []
    assert report.warnings == []


def test_invalid_inn_triggers_review():
    report, needs_review = validate_requisites(make_data(inn="1234567890"))
    assert needs_review
    assert any("checksum" in e for e in report.errors)


def test_missing_inn_triggers_review():
    report, needs_review = validate_requisites(make_data(inn=None))
    assert needs_review
    assert any("ИНН" in e for e in report.errors)


def test_missing_ogrn_triggers_review():
    report, needs_review = validate_requisites(make_data(ogrn=None))
    assert needs_review
    assert any("ОГРН" in e for e in report.errors)


def test_bik_corr_control_key_mismatch_is_warning_not_error():
    """
    RKC-вектор из test_validators_bik_account.py, намеренно изменённый на 1
    цифру счёта, передан как correspondent_account. checking_account и bik
    остаются из clean fixture (bik="044525225" здесь заменяется на
    "040305000" только для этого вызова — это меняет и cross-check по
    checking_account, поэтому тест не утверждает, что предупреждение по
    correspondent_account единственное: проверяется точечно именно оно, через
    report.correspondent_account, а не через общий список report.warnings.
    """
    report, needs_review = validate_requisites(
        make_data(bik="040305000", correspondent_account="40102810100000010002")
    )
    assert needs_review
    assert report.correspondent_account is not None
    assert report.correspondent_account.valid is True
    assert report.correspondent_account.warning is not None
    assert "контрольный ключ" in report.correspondent_account.warning
    assert report.correspondent_account.warning in report.warnings
    assert not any("контрольный ключ" in e for e in report.errors)


def test_checking_account_default_pair_mismatch_is_warning_only():
    """
    Исходная (не подогнанная) пара БИК 044525225 + р/с 40702810000000012345 не
    согласована по контрольному ключу. БИК и correspondent_account остаются из
    clean fixture без изменений, поэтому здесь report.errors == [] безопасно
    утверждать целиком (никакое другое поле не меняется).
    """
    report, needs_review = validate_requisites(
        make_data(checking_account="40702810000000012345")
    )
    assert needs_review
    assert report.errors == []
    assert report.checking_account is not None
    assert report.checking_account.valid is True
    assert report.checking_account.warning is not None
    assert "контрольный ключ" in report.checking_account.warning
    assert report.checking_account.warning in report.warnings


def test_all_missing_fields():
    data = RequisitesData()
    report, needs_review = validate_requisites(data)
    assert needs_review
    assert len(report.errors) >= 6


def test_report_has_field_results():
    report, _ = validate_requisites(make_data())
    assert report.inn is not None
    assert report.inn.valid
    assert report.bik is not None
    assert report.bik.valid


def test_review_reasons_populated_on_invalid_field():
    """review_reasons содержит читаемое описание при невалидном поле."""
    from app.schemas.requisites import RequisitesData
    from app.services.validation_service import validate_requisites
    data = RequisitesData(inn="123456789012")  # битая контрольная сумма
    report, needs_review = validate_requisites(data)
    assert needs_review
    assert any("ИНН" in r for r in report.review_reasons)

def test_invalid_field_cleared_from_data():
    """Невалидное значение поля обнуляется в data после валидации."""
    from app.schemas.requisites import RequisitesData
    from app.services.validation_service import validate_requisites
    data = RequisitesData(inn="123456789012")
    validate_requisites(data)
    assert data.inn is None

def test_ogrn_classifier_cleared_and_in_review_reasons():
    """ОКПО в поле ОГРН отклоняется, поле обнуляется, причина в review_reasons."""
    from app.schemas.requisites import RequisitesData
    from app.services.validation_service import validate_requisites
    data = RequisitesData(ogrn="12345678")  # 8 цифр — ОКПО
    report, needs_review = validate_requisites(data)
    assert needs_review
    assert data.ogrn is None
    assert any("ОГРН" in r for r in report.review_reasons)

def test_review_reasons_empty_on_all_none():
    """Если все поля None — review_reasons только про отсутствие полей."""
    from app.schemas.requisites import RequisitesData
    from app.services.validation_service import validate_requisites
    data = RequisitesData()
    report, needs_review = validate_requisites(data)
    assert needs_review
    assert all("отсутствует" in r for r in report.review_reasons)


def test_report_covers_all_sixteen_fields():
    """ValidationReport покрывает все 16 полей RequisitesData, не только 6 исходных."""
    report, _ = validate_requisites(make_data())
    for key in RequisitesData.model_fields:
        assert getattr(report, key) is not None, f"missing field result for {key}"


def test_missing_optional_field_is_missing_not_error():
    """
    email отсутствует — это is_missing, не ошибка: не попадает в errors и само
    по себе не создаёт needs_review при прочих чистых полях.
    """
    report, needs_review = validate_requisites(make_data(email=None))
    assert report.email is not None
    assert report.email.is_missing is True
    assert report.email.valid is True
    assert not any("email" in e.lower() for e in report.errors)
    assert needs_review is False


def test_bik_warning_is_aggregated_without_errors(monkeypatch):
    """
    Оркестрационная проверка переноса warning БИК в report.warnings.
    validate_bik подменяется точечно (через monkeypatch на имя, импортированное
    в app.services.validation_service), а не через make_data(bik=...), чтобы не
    создавать побочных warnings по checking/correspondent account через
    контрольный ключ — тот сценарий отдельно покрыт тестами выше и в
    test_validators_bik_account.py. normalized_value подмены равен реальному
    чистому БИК (044525225), поэтому cross-check по счетам остаётся тихим.
    Тест не утверждает, что это предупреждение единственное в отчёте.
    """
    import app.services.validation_service as vs
    from app.schemas.validation import FieldValidation

    fake_bik_result = FieldValidation(
        valid=True,
        raw_value="044525225",
        normalized_value="044525225",
        value="044525225",
        warning="Тестовое предупреждение БИК",
    )
    monkeypatch.setattr(vs, "validate_bik", lambda value: fake_bik_result)

    report, needs_review = validate_requisites(make_data())

    assert report.errors == []
    assert needs_review is True
    assert report.bik is not None
    assert report.bik.warning == "Тестовое предупреждение БИК"
    assert report.bik.warning in report.warnings
