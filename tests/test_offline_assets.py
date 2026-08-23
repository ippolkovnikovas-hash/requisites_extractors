"""
Проверка того, что интерфейс не тянет ничего из сети.

Приложение локальное: страницы должны полностью отрисовываться без интернета, а
браузер пользователя — не сообщать сторонним хостам о самом факте работы с
реквизитами (CLAUDE.md, «Приватность»).

Раньше `base.html` подключал Bootstrap с `cdn.jsdelivr.net`. Тест закрывает эту
регрессию: любой внешний хост в отрендеренной странице — ошибка.
"""
import re

import pytest

from app.schemas.requisites import RequisitesData
from app.web.routes import _build_review_rows

_EXTERNAL_URL = re.compile(r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//""", re.IGNORECASE)

_VENDOR_FILES = [
    "vendor/bootstrap/bootstrap.min.css",
    "vendor/bootstrap/bootstrap.bundle.min.js",
]


@pytest.fixture
def client():
    from app.main import create_app

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def _assert_no_external_refs(html: str) -> None:
    found = _EXTERNAL_URL.findall(html)
    assert not found, f"страница ссылается на внешний хост: {found}"


def test_index_page_has_no_external_references(client):
    response = client.get("/")
    assert response.status_code == 200
    _assert_no_external_refs(response.get_data(as_text=True))


def test_review_form_has_no_external_references(client):
    """Форма с данными рендерится через тот же base.html — проверяем и её."""
    from flask import render_template

    from app.main import create_app

    app = create_app()
    with app.test_request_context():
        html = render_template(
            "result.html",
            rows=_build_review_rows(RequisitesData(inn="7744012347"), {}, None),
            document_id="offline1",
            original_filename="sample.pdf",
            fill_rate=0.1,
            warnings=[],
            confirm_required=False,
        )
    _assert_no_external_refs(html)


def test_error_page_has_no_external_references(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    _assert_no_external_refs(response.get_data(as_text=True))


@pytest.mark.parametrize("filename", _VENDOR_FILES)
def test_vendored_asset_is_served_locally(client, filename):
    response = client.get(f"/static/{filename}")
    assert response.status_code == 200
    assert len(response.data) > 10_000


@pytest.mark.parametrize("filename", _VENDOR_FILES)
def test_vendored_asset_does_not_fetch_from_network(filename):
    """В самих файлах не должно остаться ни url(https://…), ни sourceMappingURL."""
    from pathlib import Path

    content = Path("app/static") .joinpath(filename).read_text(
        encoding="utf-8", errors="replace"
    )
    assert not re.search(r"url\(\s*['\"]?https?:", content)
    assert "sourceMappingURL" not in content
