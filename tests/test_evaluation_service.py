"""Тесты сервиса замера точности."""
import json

from app.services.evaluation_service import (
    FIELDS,
    evaluate_document,
    init_ground_truth,
    load_ground_truth,
    normalize_value,
    summarize,
    values_match,
)


def test_numeric_fields_compare_digits_only():
    assert values_match("checking_account", "4070 2810 2000 0001 2345", "40702810200000012345")


def test_text_fields_ignore_case_quotes_and_spaces():
    assert values_match("company_name", 'ООО «Ромашка»', 'ооо  "ромашка"')
    assert values_match("legal_address", "г. Москва, ул. Ёлочная, 1.", "г. Москва, ул. Елочная, 1")


def test_short_fio_ignores_spaces():
    assert values_match("ceo_fio", "Иванов И. И.", "Иванов И.И.")


def test_phone_compares_set_of_numbers():
    assert values_match("phone", "8 (495) 111-22-33, +7 999 000 11 22", "+79990001122, +74951112233")
    assert normalize_value("phone", None) == ""


def test_empty_expected_means_field_absent():
    ev = evaluate_document("a.pdf", "pdf_text", {"email": ""}, {"email": None})
    assert ev.fields == {"email": True}


def test_null_expected_is_skipped():
    ev = evaluate_document("a.pdf", "pdf_text", {"inn": None, "kpp": "773601001"}, {"kpp": "773601001"})
    assert ev.fields == {"kpp": True}


def test_failed_document_counts_as_wrong():
    ev = evaluate_document("a.doc", "error", {"inn": "7707083893"}, None, error="TextExtractionError")
    assert ev.fields == {"inn": False}
    assert ev.error == "TextExtractionError"


def test_summarize_groups_by_field_and_type():
    docs = [
        evaluate_document("a", "docx", {"inn": "1", "kpp": "2"}, {"inn": "1", "kpp": "x"}),
        evaluate_document("b", "image", {"inn": "3"}, {"inn": "3"}),
    ]
    s = summarize(docs)
    assert (s.overall.correct, s.overall.total) == (2, 3)
    assert s.by_field["inn"].rate == 1.0
    assert s.by_field["kpp"].rate == 0.0
    assert s.by_doc_type["docx"].total == 2
    assert s.to_dict()["documents"][0]["correct"] == 1


def test_init_ground_truth_keeps_existing_values(tmp_path):
    path = tmp_path / "gt.json"
    path.write_text(json.dumps({"a.pdf": {"inn": "7707083893"}}), encoding="utf-8")
    added = init_ground_truth(path, ["a.pdf", "b.docx"])
    assert added == 1
    data = load_ground_truth(path)
    assert data["a.pdf"]["inn"] == "7707083893"
    assert set(data["b.docx"]) == set(FIELDS)
    assert "_readme" not in data
