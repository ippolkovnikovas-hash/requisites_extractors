"""Тесты адаптеров .odt и .doc и их маршрутизации."""
import zipfile

import pytest

from app.core.enums import DocumentType, ExtractorType
from app.core.exceptions import TextExtractionError
from app.schemas.document import DocumentInput
from app.services.routing_service import detect_document_type

_CONTENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0">
  <office:body><office:text>
    <text:h>Карточка предприятия</text:h>
    <text:p>ООО<text:s/>«Ромашка»</text:p>
    <table:table>
      <table:table-row>
        <table:table-cell><text:p>ИНН</text:p></table:table-cell>
        <table:table-cell><text:p>7707083893</text:p></table:table-cell>
      </table:table-row>
      <table:table-row>
        <table:table-cell><text:p>БИК</text:p></table:table-cell>
        <table:table-cell><text:p>044525225</text:p></table:table-cell>
      </table:table-row>
    </table:table>
  </office:text></office:body>
</office:document-content>"""


@pytest.fixture
def sample_odt(tmp_path):
    path = tmp_path / "card.odt"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        z.writestr("content.xml", _CONTENT_XML)
    return path


def test_odt_extracts_paragraphs_and_tables(sample_odt):
    from app.extractors.odt_extractor import extract_odt

    result = extract_odt(sample_odt)
    assert result.extractor_used == ExtractorType.ODF
    assert "Карточка предприятия" in result.text
    assert "ООО «Ромашка»" in result.text
    assert "ИНН | 7707083893" in result.text
    assert "БИК | 044525225" in result.text


def test_odt_broken_file_raises(tmp_path):
    from app.extractors.odt_extractor import extract_odt

    bad = tmp_path / "bad.odt"
    bad.write_bytes(b"not a zip")
    with pytest.raises(TextExtractionError):
        extract_odt(bad)


def test_doc_without_libreoffice_raises_clear_error(tmp_path, monkeypatch):
    import app.extractors.doc_extractor as de

    monkeypatch.setattr(de, "find_soffice", lambda: None)
    doc = tmp_path / "old.doc"
    doc.write_bytes(b"\xd0\xcf\x11\xe0")
    with pytest.raises(TextExtractionError, match="LibreOffice"):
        de.extract_doc(doc)


def test_doc_converts_via_soffice(tmp_path, monkeypatch, sample_docx):
    import shutil
    import subprocess

    import app.extractors.doc_extractor as de

    monkeypatch.setattr(de, "find_soffice", lambda: "soffice")

    def fake_run(cmd, **kwargs):
        outdir = cmd[cmd.index("--outdir") + 1]
        shutil.copy(sample_docx, f"{outdir}/old.docx")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(de.subprocess, "run", fake_run)
    doc = tmp_path / "old.doc"
    doc.write_bytes(b"\xd0\xcf\x11\xe0")
    result = de.extract_doc(doc)
    assert result.extractor_used == ExtractorType.LIBREOFFICE
    assert result.text


@pytest.mark.parametrize("ext,mime,expected", [
    ("doc", "application/msword", DocumentType.DOC),
    ("odt", "application/vnd.oasis.opendocument.text", DocumentType.ODT),
    ("odt", "application/zip", DocumentType.ODT),
])
def test_routing_doc_and_odt(tmp_path, ext, mime, expected):
    path = tmp_path / f"file.{ext}"
    path.write_bytes(b"x")
    doc = DocumentInput(
        document_id="t", original_filename=path.name, extension=ext, mime_type=mime,
        size_bytes=1, storage_path=path, sha256="0",
    )
    assert detect_document_type(doc) == expected


def test_pipeline_processes_odt(sample_odt, monkeypatch):
    import app.services.pipeline_service as ps
    from app.llm.mock_client import MockLLMClient

    monkeypatch.setattr(ps, "_build_llm_client", lambda: MockLLMClient())
    result = ps.run_pipeline(sample_odt, "card.odt")
    assert result.data.inn == "7707083893"
    assert result.data.bik == "044525225"
    assert result.processing_meta["doc_type"] == "odt"
