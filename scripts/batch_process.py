"""
Batch-обработка документов + отчёт (CSV/JSON).

Пример:
  python scripts/batch_process.py C:\path\to\examples -e pdf -e docx
"""

import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import click
from loguru import logger

# Добавляем корень проекта в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.logging_config import setup_logging
from app.services.pipeline_service import run_pipeline
from app.core.exceptions import AppException
from app.schemas.validation import PipelineResult  # тип для подсказок, не обязателен


@click.command()
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--ext",
    "-e",
    multiple=True,
    default=["pdf", "docx"],
    help="Расширения файлов для обработки (можно несколько: -e pdf -e docx)",
)
@click.option(
    "--prompt-version",
    "-p",
    default=None,
    help="Версия промпта (например, v1 или v2)",
)
@click.option(
    "--report-name",
    default="batch_report",
    help="Базовое имя отчёта (без расширения)",
)
def main(
    folder_path: Path,
    ext: tuple[str, ...],
    prompt_version: str | None,
    report_name: str,
) -> None:
    """Обработать все файлы в папке и сохранить отчёт."""
    setup_logging()
    settings.ensure_dirs()

    if prompt_version:
        settings.prompt_version = prompt_version

    extensions = {f".{e.lstrip('.').lower()}" for e in ext}
    files = [f for f in folder_path.iterdir() if f.suffix.lower() in extensions]

    if not files:
        click.secho(
            f"Файлы с расширениями {extensions} не найдены в {folder_path}",
            fg="yellow",
        )
        raise SystemExit(0)

    click.echo(f"\n📂 Папка: {folder_path}")
    click.echo(f"📄 Найдено файлов: {len(files)}\n")

    results: list[dict[str, Any]] = []
    ok, failed, review = 0, 0, 0

    for i, file_path in enumerate(sorted(files), 1):
        click.echo(f"[{i}/{len(files)}] {file_path.name} ... ", nl=False)

        try:
            result: PipelineResult = run_pipeline(file_path, file_path.name)

            needs_review = result.needs_review
            status_icon = "⚠️" if needs_review else "✅"

            if needs_review:
                click.secho("⚠️  needs_review", fg="yellow")
                review += 1
            else:
                click.secho("✅ done", fg="green")
                ok += 1

            results.append(
                {
                    "file_name": file_path.name,
                    "document_id": result.document_id,
                    "status": result.status,
                    "needs_review": needs_review,
                    "fill_rate": result.fill_rate,
                    "warnings": list(result.warnings or []),
                    "json_path": result.json_path,
                    "xlsx_path": result.xlsx_path,
                    "docx_path": result.docx_path,
                }
            )

        except AppException as e:
            click.secho(f"❌ {e.message}", fg="red")
            logger.error(f"Batch error for {file_path}: {e.message} | {e.details}")
            failed += 1

            results.append(
                {
                    "file_name": file_path.name,
                    "document_id": None,
                    "status": "error",
                    "needs_review": None,
                    "fill_rate": None,
                    "warnings": [e.message],
                    "json_path": None,
                    "xlsx_path": None,
                    "docx_path": None,
                }
            )
        except Exception as e:  # pragma: no cover
            click.secho(f"❌ {e}", fg="red")
            logger.exception(f"Unexpected error for {file_path}")
            failed += 1

            results.append(
                {
                    "file_name": file_path.name,
                    "document_id": None,
                    "status": "exception",
                    "needs_review": None,
                    "fill_rate": None,
                    "warnings": [str(e)],
                    "json_path": None,
                    "xlsx_path": None,
                    "docx_path": None,
                }
            )

    # ── Итог ──────────────────────────────────────────────────────────────────

    click.echo("\n" + "─" * 40)
    click.echo(f"✅ Успешно:      {ok}")
    click.echo(f"⚠️  На проверку: {review}")
    click.echo(f"❌ Ошибок:       {failed}")

    exports_dir = Path(settings.exports_folder)
    exports_dir.mkdir(parents=True, exist_ok=True)

    json_path = exports_dir / f"{report_name}.json"
    csv_path = exports_dir / f"{report_name}.csv"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "file_name",
                "document_id",
                "status",
                "needs_review",
                "fill_rate",
                "json_path",
                "xlsx_path",
                "docx_path",
                "warnings",
            ],
        )
        writer.writeheader()
        for row in results:
            row = row.copy()
            row["warnings"] = "; ".join(row.get("warnings") or [])
            writer.writerow(row)

    click.echo(f"\n📑 Отчёт JSON: {json_path}")
    click.echo(f"📑 Отчёт CSV:  {csv_path}\n")


if __name__ == "__main__":
    main()
