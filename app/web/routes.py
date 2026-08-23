"""
Веб-интерфейс: загрузка документа → review-форма → генерация DOCX.

Ключевой принцип формы — показывать пользователю то, что он ввёл или что было
распознано, даже если значение не прошло проверку. `validate_requisites()`
обнуляет невалидные поля в `data`, чтобы мусор не попал в шаблон, но в форму
подставляется `FieldValidation.raw_value` — иначе человек не увидит, что
именно нужно исправить.

Жёсткая ошибка блокирует `/generate` до тех пор, пока пользователь явно не
подтвердит генерацию галочкой `confirm_invalid`. Предупреждение не блокирует
никогда. Незаполненное поле — тоже не блокирует: «пусто» и «введено неверно»
это разные состояния (CLAUDE.md).

Готовый DOCX отдаётся из памяти и не сохраняется ни в `exports/`, ни где-либо
ещё.
"""

import os
import re
import uuid
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from app.exporters.docx_exporter import fill_template_to_bytes
from app.schemas.requisites import RequisitesData
from app.schemas.validation import FieldValidation, PipelineResult
from app.services.pipeline_service import run_pipeline
from app.services.validation_service import FIELD_LABELS, run_field_validators

web_bp = Blueprint("web", __name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".jpg", ".jpeg", ".png", ".tiff"}
TEMPLATE_NAME = "shablon.docx"

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


# ── Сборка строк review-формы ────────────────────────────────────────────────


def _ogrn_label(value: str | None) -> str:
    """ОГРН у юрлица 13 цифр, ОГРНИП у предпринимателя — 15."""
    digits = re.sub(r"\D", "", str(value or ""))
    return "ОГРНИП" if len(digits) == 15 else "ОГРН"


def _build_review_rows(
    data: RequisitesData,
    field_results: dict[str, FieldValidation] | None,
    source_map: dict[str, str] | None,
) -> list[dict]:
    """
    Готовит 16 строк формы: подпись, значение, ошибка, предупреждение, источник.

    Значение берётся из `raw_value` результата валидации, если он есть, — так в
    форме остаётся введённое пользователем даже после того, как
    `validate_requisites()` обнулило поле в `data`.
    """
    field_results = field_results or {}
    source_map = source_map or {}

    rows = []
    for key in RequisitesData.model_fields:
        result = field_results.get(key)

        if result is not None and result.raw_value is not None:
            value = result.raw_value
        else:
            value = getattr(data, key)

        is_hard_error = bool(result and not result.valid and not result.is_missing)

        rows.append(
            {
                "key": key,
                "label": _ogrn_label(value) if key == "ogrn" else FIELD_LABELS[key],
                "value": value or "",
                "error": result.reason if is_hard_error else None,
                "warning": result.warning if result else None,
                "source": source_map.get(key),
            }
        )
    return rows


def _source_map_from_result(result: PipelineResult) -> dict[str, str]:
    """Откуда взялось значение: fallback regex или LLM."""
    meta = result.processing_meta or {}
    fallback_fields = meta.get("fallback_fields") or []

    source_map = {field: "regex" for field in fallback_fields}
    for key in RequisitesData.model_fields:
        if key not in source_map and getattr(result.data, key):
            source_map[key] = "llm"
    return source_map


def _field_results_from_report(report) -> dict[str, FieldValidation]:
    if report is None:
        return {}
    return {
        key: getattr(report, key)
        for key in RequisitesData.model_fields
        if getattr(report, key, None) is not None
    }


def _data_from_form(form) -> RequisitesData:
    """Собирает реквизиты из полей формы. Пустая строка означает «не заполнено»."""
    values = {}
    for key in RequisitesData.model_fields:
        raw = (form.get(key) or "").strip()
        values[key] = raw or None
    return RequisitesData(**values)


# ── Роуты ────────────────────────────────────────────────────────────────────


@web_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html", rows=None)


@web_bp.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        flash("Файл не был отправлен", "error")
        return redirect(url_for("web.index"))

    file = request.files["file"]

    if not file.filename:
        flash("Файл не выбран", "error")
        return redirect(url_for("web.index"))

    if not _allowed_file(file.filename):
        flash("Неподдерживаемый формат файла", "error")
        return redirect(url_for("web.index"))

    original_name = file.filename
    filename = secure_filename(original_name)
    name, ext = os.path.splitext(filename)
    stored_name = f"{name}_{uuid.uuid4().hex[:8]}{ext}"

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    file_path = upload_folder / stored_name
    file.save(str(file_path))

    try:
        result: PipelineResult = run_pipeline(file_path, original_name)
    except Exception as exc:
        current_app.logger.exception("Ошибка при обработке файла")
        flash(f"Ошибка при обработке файла: {exc}", "error")
        return redirect(url_for("web.index"))

    rows = _build_review_rows(
        result.data,
        _field_results_from_report(result.validation),
        _source_map_from_result(result),
    )

    return render_template(
        "result.html",
        rows=rows,
        document_id=result.document_id,
        original_filename=result.original_filename,
        fill_rate=result.fill_rate,
        warnings=result.warnings,
        confirm_required=False,
    )


@web_bp.route("/generate", methods=["POST"])
def generate():
    data = _data_from_form(request.form)
    document_id = (request.form.get("document_id") or "").strip()
    confirm_invalid = bool(request.form.get("confirm_invalid"))

    field_results = run_field_validators(data)

    # Блокирует только «введено, но неверно». Незаполненное поле — не ошибка,
    # даже если оно из числа обязательных.
    hard_errors = {
        key: result
        for key, result in field_results.items()
        if not result.valid and not result.is_missing
    }

    if hard_errors and not confirm_invalid:
        return (
            render_template(
                "result.html",
                rows=_build_review_rows(data, field_results, None),
                document_id=document_id,
                original_filename=None,
                fill_rate=None,
                warnings=[],
                confirm_required=True,
            ),
            422,
        )

    template_path = Path(TEMPLATE_NAME)
    if not template_path.exists():
        flash(
            f"Шаблон «{TEMPLATE_NAME}» не найден в рабочей папке — "
            f"положите его рядом с приложением и повторите.",
            "error",
        )
        return (
            render_template(
                "result.html",
                rows=_build_review_rows(data, field_results, None),
                document_id=document_id,
                original_filename=None,
                fill_rate=None,
                warnings=[],
                confirm_required=bool(hard_errors),
            ),
            503,
        )

    buffer = fill_template_to_bytes(template_path, data)

    safe_id = secure_filename(document_id) or uuid.uuid4().hex[:8]
    return send_file(
        buffer,
        mimetype=_DOCX_MIME,
        as_attachment=True,
        download_name=f"requisites_{safe_id}.docx",
    )


@web_bp.route("/downloads/<path:filename>", methods=["GET"])
def downloads(filename: str):
    return send_from_directory(
        current_app.config["EXPORT_FOLDER"], filename, as_attachment=True
    )
