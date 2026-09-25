"""Общие фикстуры для всех тестов."""
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_docx(fixtures_dir) -> Path:
    return fixtures_dir / "sample_requisites.docx"


@pytest.fixture
def sample_pdf(fixtures_dir) -> Path:
    return fixtures_dir / "sample_requisites.pdf"