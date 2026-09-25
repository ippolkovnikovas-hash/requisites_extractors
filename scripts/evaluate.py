"""
Замер точности извлечения на папке документов с эталоном.

  # 1. Создать/дополнить шаблон эталона (все поля null) — затем заполнить вручную
  python scripts/evaluate.py requisites --init

  # 2. Прогнать pipeline и посчитать точность по полям и типам документов
  python scripts/evaluate.py requisites
  python scripts/evaluate.py requisites --provider ollama --label qwen7b
  python scripts/evaluate.py requisites --provider yandex --ocr yandex --label yandex

По умолчанию печатаются только метрики, без значений реквизитов.
--show-errors выводит ожидаемое/полученное значение по каждой ошибке (персональные данные!).

Без заполненного эталона скрипт всё равно показывает «заполнено и прошло валидацию»
по полям — грубую оценку, пока эталона нет.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import click
from loguru import logger

from app.config import settings
from app.core.constants import DOCX_EXTENSION, IMAGE_EXTENSIONS, PDF_EXTENSION
from app.logging_config import setup_logging
from app.services.evaluation_service import (
    FIELDS,
    evaluate_document,
    init_ground_truth,
    load_ground_truth,
    normalize_value,
    summarize,
)

GROUND_TRUTH_NAME = "ground_truth.json"
SUPPORTED_EXTENSIONS = {PDF_EXTENSION, DOCX_EXTENSION, "doc", "odt", *IMAGE_EXTENSIONS}


def _document_files(folder: Path) -> list[Path]:
    return sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lstrip(".").lower() in SUPPORTED_EXTENSIONS
    )


def _pct(rate: float | None) -> str:
    return "  —  " if rate is None else f"{rate * 100:5.1f}%"


@click.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--truth", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help=f"Файл эталона (по умолчанию FOLDER/{GROUND_TRUTH_NAME})")
@click.option("--init", "init_mode", is_flag=True, help="Создать/дополнить шаблон эталона и выйти")
@click.option("--provider", default=None, help="Переопределить LLM_PROVIDER (mock/ollama/openai/yandex)")
@click.option("--ocr", default=None, help="Переопределить OCR_BACKEND (tesseract/easyocr/yandex)")
@click.option("--prompt", "prompt_version", default=None, help="Переопределить PROMPT_VERSION (v1..v4)")
@click.option("--label", default=None, help="Метка прогона для имени отчёта")
@click.option("--show-errors", is_flag=True, help="Показать значения по ошибкам (персональные данные)")
def main(folder: Path, truth: Path | None, init_mode: bool, provider: str | None, ocr: str | None,
         prompt_version: str | None,
         label: str | None, show_errors: bool) -> None:
    truth_path = truth or folder / GROUND_TRUTH_NAME
    files = _document_files(folder)

    if init_mode:
        added = init_ground_truth(truth_path, [f.name for f in files])
        click.echo(f"Эталон: {truth_path} (добавлено файлов: {added}, всего документов: {len(files)})")
        return

    setup_logging(log_level="WARNING")
    settings.ensure_dirs()
    if provider:
        settings.llm_provider = provider
    if ocr:
        settings.ocr_backend = ocr
    if prompt_version:
        settings.prompt_version = prompt_version

    ground_truth = load_ground_truth(truth_path) if truth_path.exists() else {}

    from app.services.pipeline_service import run_pipeline

    evaluations = []
    filled_valid = {name: 0 for name in FIELDS}
    processed = 0
    errors_log: list[str] = []

    for i, path in enumerate(files, 1):
        click.echo(f"[{i}/{len(files)}] {path.suffix.lower():6}", nl=False)
        expected = ground_truth.get(path.name, {})
        actual: dict | None = None
        doc_type = "error"
        error = None
        try:
            result = run_pipeline(path, path.name)
            actual = result.data.model_dump()
            doc_type = result.processing_meta.get("doc_type", "unknown")
            processed += 1
            for name in FIELDS:
                if actual.get(name):
                    filled_valid[name] += 1
            click.echo(f" {doc_type:9} fill={result.fill_rate:.2f}", nl=False)
        except Exception as e:  # замер не должен падать на одном документе
            error = type(e).__name__
            click.secho(f" ошибка: {error}", fg="red", nl=False)
            logger.debug("Evaluation error", file=path.name, error=str(e))

        ev = evaluate_document(path.name, doc_type, expected, actual, error)
        evaluations.append(ev)
        click.echo(f"  эталон: {ev.correct}/{ev.total}" if ev.total else "")

        if show_errors and actual is not None:
            for name, ok in ev.fields.items():
                if not ok:
                    errors_log.append(
                        f"{path.name} | {name}: ожидалось {normalize_value(name, expected.get(name))!r}, "
                        f"получено {normalize_value(name, actual.get(name))!r}"
                    )

    summary = summarize(evaluations)

    click.echo("\n== Заполнено (после валидации) по полям, без эталона ==")
    for name in FIELDS:
        rate = filled_valid[name] / processed if processed else None
        click.echo(f"  {name:22} {_pct(rate)}  ({filled_valid[name]}/{processed})")

    if summary.overall.total:
        click.echo("\n== Точность по эталону: поля ==")
        for name, score in summary.by_field.items():
            click.echo(f"  {name:22} {_pct(score.rate)}  ({score.correct}/{score.total})")
        click.echo("\n== Точность по эталону: типы документов ==")
        for doc_type, score in summary.by_doc_type.items():
            click.echo(f"  {doc_type:22} {_pct(score.rate)}  ({score.correct}/{score.total})")
        click.echo(f"\nИТОГО: {_pct(summary.overall.rate)}  ({summary.overall.correct}/{summary.overall.total})")
    else:
        click.secho(
            f"\nЭталон пуст или не найден ({truth_path}). "
            "Создайте его: python scripts/evaluate.py FOLDER --init и заполните значения.",
            fg="yellow",
        )

    if errors_log:
        click.echo("\n== Ошибки ==")
        for line in errors_log:
            click.echo("  " + line)

    report = summary.to_dict()
    report["filled_after_validation"] = {
        name: {"filled": filled_valid[name], "processed": processed} for name in FIELDS
    }
    report["meta"] = {
        "provider": settings.llm_provider,
        "ocr_backend": settings.ocr_backend,
        "prompt_version": settings.prompt_version,
        "label": label,
        "folder": str(folder),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = settings.exports_folder / f"eval_{label + '_' if label else ''}{stamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    click.echo(f"\nОтчёт: {report_path}")


if __name__ == "__main__":
    main()
