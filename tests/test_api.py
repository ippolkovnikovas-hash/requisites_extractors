"""Тесты REST API (Flask test client, mock LLM)."""
import io
from pathlib import Path

import pytest

from app.config import settings
from app.main import create_app

PDF_FIXTURE = Path(__file__).parent / "fixtures" / "sample_requisites.pdf"


@pytest.fixture
def client(monkeypatch):
    import app.services.pipeline_service as ps
    from app.llm.mock_client import MockLLMClient

    monkeypatch.setattr(ps, "_build_llm_client", lambda: MockLLMClient())
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _upload(client, name="sample.pdf", content=None):
    content = PDF_FIXTURE.read_bytes() if content is None else content
    return client.post(
        "/api/extract",
        data={"file": (io.BytesIO(content), name)},
        content_type="multipart/form-data",
    )


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "version": "1.0.0"}


def test_extract_pdf_and_fetch_result(client):
    resp = _upload(client)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["inn"] == "7744012347"
    assert body["processing_meta"]["doc_type"] == "pdf_text"

    again = client.get(f"/api/result/{body['document_id']}")
    assert again.status_code == 200
    assert again.get_json()["document_id"] == body["document_id"]


def test_download_json(client):
    doc_id = _upload(client).get_json()["document_id"]
    resp = client.get(f"/api/download/{doc_id}/json")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].startswith("attachment")


def test_download_unknown_format(client):
    doc_id = _upload(client).get_json()["document_id"]
    resp = client.get(f"/api/download/{doc_id}/pdf")
    assert resp.status_code == 400
    assert resp.get_json()["code"] == 400


def test_result_and_download_unknown_id(client):
    assert client.get("/api/result/nope").status_code == 404
    assert client.get("/api/download/nope/json").status_code == 404


def test_extract_without_file(client):
    resp = client.post("/api/extract", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_extract_empty_filename(client):
    resp = _upload(client, name="")
    assert resp.status_code == 400


def test_extract_unsupported_extension(client):
    resp = _upload(client, name="virus.exe", content=b"MZ")
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.get_json()["details"]


def test_extract_too_large(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_mb", 0)
    resp = _upload(client)
    assert resp.status_code == 413


def test_extract_pipeline_failure_returns_500(client, monkeypatch):
    import app.api.routes_upload as ru

    def boom(*args, **kwargs):
        raise RuntimeError("broken")

    monkeypatch.setattr(ru, "run_pipeline", boom)
    resp = _upload(client)
    assert resp.status_code == 500
    assert resp.get_json()["error"] == "Internal server error"


def test_unknown_route_404(client):
    assert client.get("/api/unknown").status_code == 404


def test_test_ui_served(client):
    resp = client.get("/test")
    assert resp.status_code == 200
    assert b"<input" in resp.data
