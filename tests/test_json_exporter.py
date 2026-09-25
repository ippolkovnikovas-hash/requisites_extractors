"""Тесты JSON-экспортёра."""
import json
import pytest
from app.schemas.requisites import RequisitesData
from app.schemas.validation import ValidationReport
from app.exporters.json_exporter import export_json


def make_requisites(**kwargs):
    defaults = dict(
        inn="7744012347",
        kpp="774401001",
        ogrn="1027700123450",
        bik="044525225",
        checking_account="40702810000000012345",
        correspondent_account="30101810400000000225",
        company_name="ООО Тестовая Организация",
    )
    defaults.update(kwargs)
    return RequisitesData(**defaults)


def test_export_creates_file(tmp_path, monkeypatch):
    import app.exporters.json_exporter as je
    from unittest.mock import patch
    with patch.object(je.settings, "exports_folder", tmp_path):
        path = export_json("test-001", make_requisites(), ValidationReport(), False)
    assert path.exists()
    assert path.suffix == ".json"


def test_export_valid_json(tmp_path, monkeypatch):
    import app.exporters.json_exporter as je
    from unittest.mock import patch
    with patch.object(je.settings, "exports_folder", tmp_path):
        path = export_json("test-002", make_requisites(), ValidationReport(), False)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["document_id"] == "test-002"
    assert payload["needs_review"] is False
    assert "data" in payload
    assert "validation" in payload
    assert "data_aliases" in payload


def test_export_fill_rate(tmp_path):
    import app.exporters.json_exporter as je
    from unittest.mock import patch
    with patch.object(je.settings, "exports_folder", tmp_path):
        path = export_json("test-003", make_requisites(), ValidationReport(), False)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert 0.0 <= payload["fill_rate"] <= 1.0


def test_export_inn_in_data(tmp_path):
    import app.exporters.json_exporter as je
    from unittest.mock import patch
    with patch.object(je.settings, "exports_folder", tmp_path):
        path = export_json("test-004", make_requisites(), ValidationReport(), False)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["data"]["inn"] == "7744012347"


def test_export_needs_review_true(tmp_path):
    import app.exporters.json_exporter as je
    from unittest.mock import patch
    with patch.object(je.settings, "exports_folder", tmp_path):
        path = export_json("test-005", make_requisites(), ValidationReport(), True)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["needs_review"] is True
