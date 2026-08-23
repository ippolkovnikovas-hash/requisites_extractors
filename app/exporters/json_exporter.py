"""
Экспорт результата pipeline в JSON-файл.

Структура файла:
  document_id   — идентификатор обработки
  needs_review  — флаг ручной проверки
  fill_rate     — доля заполненных полей (0.0–1.0)
  data          — реквизиты по python-именам полей
  data_aliases  — реквизиты по плейсхолдерам shablon.docx
  validation    — отчёт валидации (inn, kpp, ogrn, bik, счета, кросс-проверки)
"""

import json
from pathlib import Path

from loguru import logger

from app.config import settings
from app.schemas.requisites import RequisitesData
from app.schemas.validation import ValidationReport


def export_json(
    document_id: str,
    requisites: RequisitesData,
    validation: ValidationReport,
    needs_review: bool,
    extracted_by: list[str] | None = None,
    processing_meta: dict | None = None,
) -> Path:
    """
    Сохраняет JSON в exports/{document_id}_result.json.
    Возвращает Path к созданному файлу.
    """
    out_path = settings.exports_folder / f"{document_id}_result.json"
    settings.exports_folder.mkdir(parents=True, exist_ok=True)

    out_path.write_text(
        build_json_payload(
            document_id, requisites, validation, needs_review,
            extracted_by, processing_meta,
        ),
        encoding="utf-8",
    )

    logger.info("JSON exported", path=str(out_path), size_bytes=out_path.stat().st_size)
    return out_path


def build_json_payload(
    document_id: str,
    requisites: RequisitesData,
    validation: ValidationReport,
    needs_review: bool,
    extracted_by: list[str] | None = None,
    processing_meta: dict | None = None,
) -> str:
    """
    Собирает тот же JSON, но возвращает строкой — без записи на диск.

    Используется в `/api/download`, где документ отдаётся пользователю сразу и
    не должен оставаться в exports/.
    """
    payload = {
        "document_id": document_id,
        "needs_review": needs_review,
        "fill_rate": requisites.fill_rate(),

        # Реквизиты по python-именам — для downstream-кода
        "data": requisites.model_dump(),

        # Реквизиты по плейсхолдерам шаблона — для быстрой сверки с shablon.docx
        "data_aliases": requisites.to_template_dict(),

        # Отчёт валидации
        "validation": validation.model_dump(),
        "extracted_by": extracted_by or [],
        "processing_meta": processing_meta or {},
    }

    return json.dumps(payload, ensure_ascii=False, indent=2)
