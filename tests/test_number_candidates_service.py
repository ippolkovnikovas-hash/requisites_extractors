"""Тесты выбора числовых реквизитов по кандидатам и контрольным суммам."""
from app.services.number_candidates_service import (
    apply_number_candidates,
    find_digit_candidates,
    select_requisite_numbers,
)

# Валидные по контрольным суммам значения
INN = "7707083893"
KPP = "773601001"
OGRN = "1027700132195"
BIK = "044525225"
KS = "30101810400000000225"
RS = "40702810200000012345"  # ключ сходится с BIK
RS_BAD_KEY = "40702810000000012345"


def test_candidates_join_spaced_groups():
    values = {c.value for c in find_digit_candidates("р/с 4070 2810 2000 0001 2345")}
    assert RS in values


def test_candidates_split_adjacent_numbers():
    values = {c.value for c in find_digit_candidates(f"{INN} {KPP}")}
    assert INN in values
    assert KPP in values


def test_candidates_fix_ocr_letters_between_digits():
    values = {c.value for c in find_digit_candidates("ИНН 77О7О83893")}
    assert INN in values


def test_select_basic_card():
    text = f"""ИНН {INN}
КПП {KPP}
ОГРН {OGRN}
БИК {BIK}
к/с {KS}
р/с {RS}"""
    assert select_requisite_numbers(text) == {
        "inn": INN,
        "kpp": KPP,
        "ogrn": OGRN,
        "bik": BIK,
        "correspondent_account": KS,
        "checking_account": RS,
    }


def test_select_inn_kpp_combined_label():
    result = select_requisite_numbers(f"ИНН/КПП {INN}/{KPP}")
    assert result["inn"] == INN
    assert result["kpp"] == KPP


def test_select_rejects_invalid_checksum():
    result = select_requisite_numbers("ИНН 7707083890")
    assert result["inn"] is None


def test_select_ignores_bank_inn_and_classifiers():
    text = f"""ИНН банка {INN}
ОКПО 1027700132195"""
    result = select_requisite_numbers(text)
    assert result["inn"] is None
    assert result["ogrn"] is None


def test_select_org_inn_before_bank_inn():
    text = f"""ИНН 7736050003
Банк: ПАО Сбербанк ИНН {INN}"""
    assert select_requisite_numbers(text)["inn"] == "7736050003"


def test_select_kpp_requires_label():
    assert select_requisite_numbers(f"Код {KPP}")["kpp"] is None


def test_select_prefers_account_matching_bik_key():
    text = f"""БИК {BIK}
к/с {KS}
Счёт {RS_BAD_KEY}
Счёт {RS}"""
    assert select_requisite_numbers(text)["checking_account"] == RS


def test_hint_breaks_tie_between_unlabeled_candidates():
    text = f"{RS} {RS_BAD_KEY.replace('4070', '4080', 1)}"
    result = select_requisite_numbers(text, hints={"checking_account": RS})
    assert result["checking_account"] == RS


def test_apply_overrides_wrong_llm_value_and_marks_source():
    data = {"inn": "7707083890", "kpp": None, "company_name": "ООО Ромашка"}
    merged, sources = apply_number_candidates(data, f"ИНН {INN}", {"inn": "llm"})
    assert merged["inn"] == INN
    assert sources["inn"] == "checksum"
    assert merged["company_name"] == "ООО Ромашка"


def test_apply_keeps_value_when_no_candidate():
    data = {"inn": "7707083893"}
    merged, sources = apply_number_candidates(data, "нет чисел", {"inn": "llm"})
    assert merged["inn"] == "7707083893"
    assert sources["inn"] == "llm"
