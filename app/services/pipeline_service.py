"""
Центральный оркестратор pipeline.

Этапы:
  1. DocumentInput    — принять файл, вычислить sha256, определить расширение/MIME
  2. Routing          — определить DocumentType
  3. Text extraction  — извлечь сырой текст нужным экстрактором
  4. Normalization    — почистить текст перед LLM
  5. LLM extraction   — получить структурированный JSON
  6. Parse            — разобрать JSON в RequisitesData
  7. Validation       — проверить форматы и кросс-связи полей
  8. Export           — JSON + XLSX + заполненный shablon.docx
  9. PipelineResult   — вернуть итог
"""

import hashlib
import uuid
from pathlib import Path

from loguru import logger

from app.config import settings
from app.core.constants import NORMALIZE_MAX_CHARS
from app.core.enums import DocumentType, LLMProvider
from app.core.exceptions import UnsupportedFileTypeError
from app.exporters.json_exporter import export_json
from app.exporters.xlsx_exporter import export_xlsx
from app.schemas.document import DocumentInput
from app.schemas.requisites import RequisitesData
from app.schemas.validation import PipelineResult
from app.services.fallback_regex_service import (
    extract_fallback_fields,
    merge_llm_and_fallback,
)
from app.services.routing_service import detect_document_type
from app.services.text_extraction_service import extract_text
from app.services.text_normalization_service import normalize_text
from app.services.validation_service import validate_requisites

_REQUISITES_FIELDS: frozenset[str] = frozenset(RequisitesData.model_fields.keys())


def _build_llm_client():
    """Выбираем LLM-клиент по настройке LLM_PROVIDER из .env."""
    provider = settings.llm_provider.lower()

    if provider == LLMProvider.OLLAMA:
        from app.llm.ollama_client import OllamaClient
        return OllamaClient()

    if provider == LLMProvider.OPENAI:
        api_key = settings.openai_api_key
        if not api_key or api_key.lower() in ("none", ""):
            logger.warning(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is missing — falling back to mock"
            )
            from app.llm.mock_client import MockLLMClient
            return MockLLMClient()
        from app.llm.openai_client import OpenAIClient
        return OpenAIClient()

    if provider == LLMProvider.MOCK:
        from app.llm.mock_client import MockLLMClient
        return MockLLMClient()

    logger.warning("Unknown LLM_PROVIDER={}, falling back to mock", provider)
    from app.llm.mock_client import MockLLMClient
    return MockLLMClient()


def _guess_mime(path: Path) -> str:
    try:
        import magic
        return magic.from_file(str(path), mime=True)
    except Exception:
        mapping = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".tiff": "image/tiff",
        }
        return mapping.get(path.suffix.lower(), "application/octet-stream")


def _build_review_warnings(
    requisites: RequisitesData,
    validation_report,
    extraction_warnings: list[str],
    normalized_char_count_before: int,
) -> list[str]:
    warnings = extraction_warnings.copy()

    if normalized_char_count_before > NORMALIZE_MAX_CHARS:
        warnings.append(f"Text truncated: {normalized_char_count_before} → {NORMALIZE_MAX_CHARS} chars")

    if validation_report.errors:
        warnings.extend(validation_report.errors)

    missing_fields = requisites.missing_fields()
    if missing_fields:
        warnings.append("Missing fields: " + ", ".join(missing_fields))

    return list(dict.fromkeys(warnings))


def run_pipeline(file_path: Path, original_filename: str) -> PipelineResult:
    document_id = str(uuid.uuid4())[:8]

    logger.info(
        "═══ Pipeline started ═══",
        document_id=document_id,
        file=original_filename,
        size_kb=round(file_path.stat().st_size / 1024, 1),
    )

    # ── 1. DocumentInput ─────────────────────────────────────────────────
    sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()

    doc = DocumentInput(
        document_id=document_id,
        original_filename=original_filename,
        extension=file_path.suffix.lstrip(".").lower(),
        mime_type=_guess_mime(file_path),
        size_bytes=file_path.stat().st_size,
        storage_path=file_path,
        sha256=sha256,
    )

    # ── 2. Routing ───────────────────────────────────────────────────────
    doc.doc_type = detect_document_type(doc)
    if doc.doc_type == DocumentType.UNSUPPORTED:
        raise UnsupportedFileTypeError(
            f"Unsupported file type: .{doc.extension}",
            {"file": original_filename},
        )
    logger.info("Step 2/9 routing done", doc_type=doc.doc_type)

    # ── 3. Text extraction ───────────────────────────────────────────────
    extraction = extract_text(doc)
    logger.info(
        "Step 3/9 text extracted",
        extractor=extraction.extractor_used,
        chars=len(extraction.text),
        ocr=extraction.ocr_used,
        warnings=len(extraction.warnings),
    )

    settings.processed_folder.mkdir(parents=True, exist_ok=True)
    raw_text_path = settings.processed_folder / f"{document_id}_raw.txt"
    raw_text_path.write_text(extraction.text, encoding="utf-8")

    # ── 4. Normalization ─────────────────────────────────────────────────
    norm = normalize_text(extraction.text)
    logger.info(
        "Step 4/9 normalization done",
        before=norm.char_count_before,
        after=norm.char_count_after,
    )

    (settings.processed_folder / f"{document_id}_normalized.txt").write_text(
        norm.normalized_text, encoding="utf-8"
    )

    # ── 5. LLM extraction ────────────────────────────────────────────────
    llm_client = _build_llm_client()
    llm_result = llm_client.extract(norm.normalized_text, settings.prompt_version)
    logger.info(
        "Step 5/9 LLM done",
        provider=llm_result.provider,
        model=llm_result.model_name,
        prompt_version=llm_result.prompt_version,
    )

    # ── 6. Parse → merge LLM + fallback regex → RequisitesData ──────────
    safe_data = {
        k: v
        for k, v in llm_result.parsed_data.items()
        if k in _REQUISITES_FIELDS
    }

    fallback_data = extract_fallback_fields(norm.normalized_text)
    merged_data, extracted_by = merge_llm_and_fallback(safe_data, fallback_data)

    requisites = RequisitesData(**merged_data)

    logger.debug("LLM safe_data", safe_data=safe_data)
    logger.debug("Fallback data", fallback_data=fallback_data)
    logger.debug("Merged data", merged_data=merged_data)

    logger.info(
        "Step 6/9 parsed",
        filled=len(requisites.filled_fields()),
        missing=len(requisites.missing_fields()),
        fill_rate=requisites.fill_rate(),
        extracted_by=extracted_by,
    )

    if not requisites.company_name and requisites.short_name:
        requisites.company_name = requisites.short_name

    # ── 7. Validation ────────────────────────────────────────────────────
    validation_report, needs_review = validate_requisites(requisites)

    logger.info(
        "Step 7/9 validation done",
        needs_review=needs_review,
        errors=validation_report.errors,
    )

    # ── 8. Export ────────────────────────────────────────────────────────
    settings.exports_folder.mkdir(parents=True, exist_ok=True)

    json_path = export_json(
        document_id,
        requisites,
        validation_report,
        needs_review,
        extracted_by=extracted_by,
        processing_meta={
            "extractor": extraction.extractor_used,
            "ocr_used": extraction.ocr_used,
            "llm_provider": llm_result.provider,
            "llm_model": llm_result.model_name,
            "prompt_version": llm_result.prompt_version,
            "sha256": sha256,
            "fallback_used": bool(extracted_by),
            "fallback_count": len(extracted_by),
        },
    )
    logger.info("Step 8/9 JSON saved", path=json_path.name)

    xlsx_path = export_xlsx(document_id, requisites, validation_report)
    logger.info("Step 8/9 XLSX saved", path=xlsx_path.name)

    docx_path: str | None = None
    template_path = Path("shablon.docx")
    if template_path.exists():
        try:
            from app.exporters.docx_exporter import fill_template

            out_docx = settings.exports_folder / f"{document_id}_result.docx"
            fill_template(template_path, requisites, out_docx)
            docx_path = str(out_docx)
            logger.info("Step 8/9 DOCX filled", path=out_docx.name)
        except Exception as e:
            logger.warning("DOCX export failed", reason=str(e))
    else:
        logger.debug("shablon.docx not found, DOCX export skipped")

    # ── 9. Result ────────────────────────────────────────────────────────
    all_warnings = _build_review_warnings(
        requisites=requisites,
        validation_report=validation_report,
        extraction_warnings=extraction.warnings,
        normalized_char_count_before=norm.char_count_before,
    )

    status = "needs_review" if needs_review else "done"

    result = PipelineResult(
        document_id=document_id,
        original_filename=original_filename,
        data=requisites,
        validation=validation_report,
        needs_review=needs_review,
        warnings=all_warnings,
        status=status,
        fill_rate=requisites.fill_rate(),
        raw_text_path=str(raw_text_path),
        json_path=str(json_path),
        xlsx_path=str(xlsx_path),
        docx_path=docx_path,
        processing_meta={
            "extractor": extraction.extractor_used,
            "ocr_used": extraction.ocr_used,
            "llm_provider": llm_result.provider,
            "llm_model": llm_result.model_name,
            "prompt_version": llm_result.prompt_version,
            "sha256": sha256,
            "fallback_used": bool(extracted_by),
            "fallback_fields": extracted_by,
            "fallback_count": len(extracted_by),
        },
    )

    logger.info(
        "═══ Pipeline completed ═══",
        document_id=document_id,
        status=result.status,
        fill_rate=result.fill_rate,
        needs_review=needs_review,
        json=json_path.name,
        xlsx=xlsx_path.name,
        docx=Path(docx_path).name if docx_path else None,
    )

    return result
