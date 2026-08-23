"""
Тесты опционального сохранения артефактов pipeline.

Правило из CLAUDE.md: результат обработки не должен оставаться на диске после
отдачи ответа. Поэтому по умолчанию pipeline не пишет ничего — ни сырой и
нормализованный текст в processed/, ни JSON/XLSX/DOCX в exports/. Сохранение
включается явно: флагом `persist=True` или настройкой `PERSIST_ARTIFACTS`.

Пути к артефактам в PipelineResult при выключенном сохранении равны None — это
и есть признак того, что файла нет, а не пустая строка.
"""

import shutil

import pytest

from app.config import settings
from app.services.pipeline_service import run_pipeline

PDF_FIXTURE = "tests/fixtures/sample_requisites.pdf"


@pytest.fixture(autouse=True)
def use_mock_llm(monkeypatch):
    import app.services.pipeline_service as ps
    from app.llm.mock_client import MockLLMClient

    monkeypatch.setattr(ps, "_build_llm_client", lambda: MockLLMClient())


@pytest.fixture
def pdf(tmp_path):
    target = tmp_path / "sample.pdf"
    shutil.copy(PDF_FIXTURE, target)
    return target


# ── По умолчанию не сохраняем ────────────────────────────────────────────────


def test_pipeline_writes_no_files_by_default(pdf, tmp_path):
    result = run_pipeline(pdf, "sample.pdf")

    assert result.raw_text_path is None
    assert result.json_path is None
    assert result.xlsx_path is None
    assert result.docx_path is None


def test_pipeline_does_not_create_folders_by_default(pdf, tmp_path):
    run_pipeline(pdf, "sample.pdf")

    assert not (tmp_path / "exports").exists()
    assert not (tmp_path / "processed").exists()


def test_pipeline_still_returns_full_result_without_persisting(pdf):
    """Отказ от записи на диск не должен обеднять сам результат."""
    result = run_pipeline(pdf, "sample.pdf")

    assert result.document_id
    assert result.data.inn == "7744012347"
    assert result.validation.inn is not None
    assert result.fill_rate > 0


# ── Явное включение через аргумент ───────────────────────────────────────────


def test_pipeline_persists_when_asked_explicitly(pdf, tmp_path):
    result = run_pipeline(pdf, "sample.pdf", persist=True)

    assert result.json_path is not None
    assert result.xlsx_path is not None
    assert result.raw_text_path is not None

    from pathlib import Path

    assert Path(result.json_path).exists()
    assert Path(result.xlsx_path).exists()
    assert Path(result.raw_text_path).exists()


def test_pipeline_persist_writes_into_configured_folders(pdf, tmp_path):
    run_pipeline(pdf, "sample.pdf", persist=True)

    assert list((tmp_path / "exports").glob("*_result.json"))
    assert list((tmp_path / "processed").glob("*_raw.txt"))
    assert list((tmp_path / "processed").glob("*_normalized.txt"))


# ── Включение через настройку ────────────────────────────────────────────────


def test_pipeline_persist_follows_settings_when_argument_omitted(pdf, monkeypatch):
    monkeypatch.setattr(settings, "persist_artifacts", True)

    result = run_pipeline(pdf, "sample.pdf")

    assert result.json_path is not None


def test_explicit_argument_overrides_enabled_setting(pdf, monkeypatch, tmp_path):
    """persist=False сильнее включённой настройки."""
    monkeypatch.setattr(settings, "persist_artifacts", True)

    result = run_pipeline(pdf, "sample.pdf", persist=False)

    assert result.json_path is None
    assert not (tmp_path / "exports").exists()


def test_persist_artifacts_defaults_to_false():
    """Значение по умолчанию — не хранить: приватность важнее удобства."""
    assert settings.persist_artifacts is False
