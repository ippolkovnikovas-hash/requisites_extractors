import pathlib as _pl
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, abort
from loguru import logger

from app.dependencies import validate_upload
from app.services.pipeline_service import run_pipeline

upload_bp = Blueprint("upload", __name__, url_prefix="/api")

_results: dict[str, dict] = {}


@upload_bp.post("/extract")
def extract():
    data, filename = validate_upload(request)

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(filename).suffix
    ) as tmp:
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
    _results[result.document_id] = payload
    return jsonify(payload), 200


@upload_bp.get("/result/<document_id>")
def get_result(document_id: str):
    if document_id not in _results:
        abort(404, description=f"No result for document_id={document_id!r}")
    return jsonify(_results[document_id]), 200


@upload_bp.get("/download/<document_id>/<fmt>")
def download(document_id: str, fmt: str):
    if document_id not in _results:
        abort(404, description=f"No result for document_id={document_id!r}")

    result = _results[document_id]
    fmt = fmt.lower()

    path_map = {
        "json": result.get("json_path"),
        "xlsx": result.get("xlsx_path"),
        "docx": result.get("docx_path"),
    }
    if fmt not in path_map:
        abort(400, description=f"Unknown format {fmt!r}. Supported: json, xlsx, docx")

    file_path = path_map[fmt]
    if not file_path:
        abort(404, description=f"File not found for format={fmt!r}")

    abs_path = Path(file_path)
    if not abs_path.is_absolute():
        abs_path = _pl.Path.cwd() / abs_path
    if not abs_path.exists():
        abort(404, description=f"File not found: {abs_path}")

    return send_file(str(abs_path), as_attachment=True)


def _serialize(result) -> dict:
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
