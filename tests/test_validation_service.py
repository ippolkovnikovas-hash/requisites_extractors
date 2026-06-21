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
        checking_account="40702810000000012345",
        correspondent_account="30101810400000000225",
    )
    defaults.update(kwargs)
    return RequisitesData(**defaults)


def test_valid_requisites_no_review():
    report, needs_review = validate_requisites(make_data())
    assert not needs_review
    assert report.errors == []


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


def test_bik_corr_mismatch_triggers_review():
    report, needs_review = validate_requisites(
        make_data(correspondent_account="30101810400000000999")
    )
    assert needs_review
    assert any("mismatch" in e for e in report.errors)


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
