"""Общие фикстуры для всех тестов."""
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolate_artifact_folders(tmp_path, monkeypatch):
    """
    Уводит рабочие папки приложения во временный каталог теста.

    Без этого каждый прогон pytest писал результаты pipeline прямо в exports/ и
    processed/ репозитория: там накапливались тысячи файлов с распознанными
    реквизитами. Фикстура autouse — изоляция не должна зависеть от того,
    вспомнил ли автор теста про неё.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "exports_folder", tmp_path / "exports")
    monkeypatch.setattr(settings, "processed_folder", tmp_path / "processed")
    monkeypatch.setattr(settings, "upload_folder", tmp_path / "uploads")


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_docx(fixtures_dir) -> Path:
    return fixtures_dir / "sample_requisites.docx"


@pytest.fixture
def sample_pdf(fixtures_dir) -> Path:
    return fixtures_dir / "sample_requisites.pdf"
