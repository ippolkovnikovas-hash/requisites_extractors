"""
REST-эндпоинты обработки документа.

Артефакты на диск не сохраняются: `run_pipeline` вызывается без `persist`, а
`/api/download` собирает запрошенный формат на лету из результата, который
остался в памяти. Так документ не переживает ответ и не накапливается в
`exports/` (CLAUDE.md).

Результаты держатся в словаре процесса — этого достаточно для локального
однопользовательского приложения и не требует БД.
"""

import io
import tempfile
from pathlib import Path

from flask import Blueprint, abort, jsonify, request, send_file
from loguru import logger

from app.dependencies import validate_upload
from app.exporters.docx_exporter import fill_template_to_bytes
from app.exporters.json_exporter import build_json_payload
from app.exporters.xlsx_exporter import export_xlsx_to_bytes
from app.schemas.validation import PipelineResult
from app.services.pipeline_service import run_pipeline

upload_bp = Blueprint("upload", __name__, url_prefix="/api")

TEMPLATE_NAME = "shablon.docx"

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# document_id → (сериализованный ответ, полный результат для пересборки файлов)
_results: dict[str, tuple[dict, PipelineResult]] = {}


@upload_bp.post("/extract")
def extract():
    data, filename = validate_upload(request)

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        result = run_pipeline(tmp_path, original_filename=filename)
    except Exception as e:
        logger.exception("Pipeline failed", filename=filename)
        abort(500, description=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

    payload = _serialize(result)
    _results[result.document_id] = (payload, result)
    return jsonify(payload), 200


@upload_bp.get("/result/<document_id>")
def get_result(document_id: str):
    entry = _results.get(document_id)
    if entry is None:
        abort(404, description=f"No result for document_id={document_id!r}")
    return jsonify(entry[0]), 200


@upload_bp.get("/download/<document_id>/<fmt>")
def download(document_id: str, fmt: str):
    entry = _results.get(document_id)
    if entry is None:
        abort(404, description=f"No result for document_id={document_id!r}")

    result = entry[1]
    fmt = fmt.lower()

    if fmt == "json":
        payload = build_json_payload(
            result.document_id,
            result.data,
            result.validation,
            result.needs_review,
            processing_meta=result.processing_meta,
        )
        return _attachment(
            io.BytesIO(payload.encode("utf-8")),
            "application/json",
            f"{document_id}_result.json",
        )

    if fmt == "xlsx":
        return _attachment(
            export_xlsx_to_bytes(result.data, result.validation),
            _XLSX_MIME,
            f"{document_id}_result.xlsx",
        )

    if fmt == "docx":
        template_path = Path(TEMPLATE_NAME)
        if not template_path.exists():
            abort(
                503,
                description=(
                    f"Template {TEMPLATE_NAME!r} not found in working directory"
                ),
            )
        return _attachment(
            fill_template_to_bytes(template_path, result.data),
            _DOCX_MIME,
            f"{document_id}_result.docx",
        )

    abort(400, description=f"Unknown format {fmt!r}. Supported: json, xlsx, docx")


def _attachment(buffer: io.BytesIO, mimetype: str, filename: str):
    return send_file(
        buffer, mimetype=mimetype, as_attachment=True, download_name=filename
    )


def _serialize(result: PipelineResult) -> dict:
    return {
        "document_id": result.document_id,
        "status": result.status,
        "needs_review": result.needs_review,
        "fill_rate": result.fill_rate,
        "data": result.data.model_dump(),
        "validation": result.validation.model_dump(),
        "warnings": result.warnings,
        "processing_meta": result.processing_meta,
        "json_path": result.json_path,
        "xlsx_path": result.xlsx_path,
        "docx_path": result.docx_path,
    }
