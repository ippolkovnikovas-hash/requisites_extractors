r"""
Замер field-level accuracy на реальных документах (ROADMAP, эпик Э11).

Для каждого документа в папке ищет рядом файл `<имя>.expected.json` с
эталонными значениями: 16 полей RequisitesData под python-именами
(company_name, inn, kpp, ...), null или пропуск ключа для полей, которых в
документе действительно нет. Пример `card1.pdf` → `card1.expected.json`:

  {
    "company_name": "Общество с ограниченной ответственностью «Ромашка»",
    "inn": "7801234567",
    "kpp": null
  }

Документ прогоняется через pipeline, результат сравнивается с эталоном
значение за значением — см. `app/services/accuracy_service.py` за тем, что
именно считается совпадением, пропуском или придуманным значением.

Документы и *.expected.json — это реальные реквизиты, они не должны попасть
в Git (CLAUDE.md): держите их вне репозитория, как и в `batch_process.py`.
Отчёт со сводкой точности пишется в `exports/`, тоже вне Git.

Пример:
  python scripts/measure_accuracy.py C:\path\to\real_samples
"""

import json
import sys
from pathlib import Path

import click
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.core.exceptions import AppException
from app.logging_config import setup_logging
from app.schemas.requisites import RequisitesData
from app.services.accuracy_service import (
    FieldOutcome,
    aggregate_field_accuracy,
    compare_document,
    overall_accuracy,
)
from app.services.pipeline_service import run_pipeline

_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".jpg", ".jpeg", ".png", ".tiff"}
_PROBLEM_OUTCOMES = {
    FieldOutcome.MISMATCH,
    FieldOutcome.MISSING,
    FieldOutcome.FALSE_POSITIVE,
}


def _load_expected(path: Path) -> RequisitesData:
    data = json.loads(path.read_text(encoding="utf-8"))
    return RequisitesData(**data)


@click.command()
@click.argument(
    "folder_path", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option(
    "--report-name",
    default="accuracy_report",
    help="Базовое имя отчёта (без расширения)",
)
def main(folder_path: Path, report_name: str) -> None:
    """Сравнить извлечение с эталоном для каждого документа в папке."""
    setup_logging()
    settings.ensure_dirs()

    documents = sorted(
        f for f in folder_path.iterdir() if f.suffix.lower() in _DOCUMENT_EXTENSIONS
    )
    if not documents:
        click.secho(f"Документы не найдены в {folder_path}", fg="yellow")
        raise SystemExit(0)

    click.echo(f"\n📂 Папка: {folder_path}")
    click.echo(f"📄 Найдено документов: {len(documents)}\n")

    per_document_outcomes: list[dict[str, str]] = []
    per_document_rows: list[dict] = []
    skipped = 0
    failed = 0

    for doc_path in documents:
        expected_path = doc_path.with_suffix(".expected.json")

        if not expected_path.exists():
            click.secho(
                f"[skip]  {doc_path.name}: нет {expected_path.name}", fg="yellow"
            )
            skipped += 1
            continue

        try:
            expected = _load_expected(expected_path)
        except Exception as e:
            click.secho(
                f"[skip]  {doc_path.name}: не разобрать эталон — {e}", fg="yellow"
            )
            skipped += 1
            continue

        try:
            result = run_pipeline(doc_path, doc_path.name, persist=False)
        except AppException as e:
            click.secho(f"[error] {doc_path.name}: {e.message}", fg="red")
            logger.error(
                "Accuracy measurement failed", file=doc_path.name, reason=e.message
            )
            failed += 1
            continue

        outcomes = compare_document(expected, result.data)
        per_document_outcomes.append(outcomes)

        problems = sorted(f for f, o in outcomes.items() if o in _PROBLEM_OUTCOMES)
        if problems:
            click.secho(f"[warn]  {doc_path.name}: {', '.join(problems)}", fg="yellow")
        else:
            click.secho(f"[ok]    {doc_path.name}", fg="green")

        per_document_rows.append({"file_name": doc_path.name, "outcomes": outcomes})

    if not per_document_outcomes:
        click.secho(
            "\nНи одного документа не сравнили — нечего измерять "
            "(проверьте, что рядом с документами лежат *.expected.json).",
            fg="red",
        )
        raise SystemExit(1)

    field_report = aggregate_field_accuracy(per_document_outcomes)
    overall = overall_accuracy(field_report)

    click.echo("\n" + "─" * 60)
    click.echo(
        f"{'Поле':<24}{'Точность':>10}{'match':>8}{'mismatch':>10}"
        f"{'missing':>9}{'false+':>8}"
    )
    for field in sorted(field_report):
        r = field_report[field]
        accuracy_str = f"{r['accuracy']:.0%}" if r["accuracy"] is not None else "—"
        click.echo(
            f"{field:<24}{accuracy_str:>10}{r['match']:>8}{r['mismatch']:>10}"
            f"{r['missing']:>9}{r['false_positive']:>8}"
        )
    click.echo("─" * 60)

    overall_str = f"{overall:.1%}" if overall is not None else "—"
    click.echo(f"\nОбщая точность: {overall_str}")
    click.echo(f"Сравнено:       {len(per_document_outcomes)}")
    click.echo(f"Пропущено:      {skipped} (нет эталона)")
    click.echo(f"Ошибок pipeline:{failed:>2}")

    exports_dir = Path(settings.exports_folder)
    exports_dir.mkdir(parents=True, exist_ok=True)
    report_path = exports_dir / f"{report_name}.json"
    report_path.write_text(
        json.dumps(
            {
                "overall_accuracy": overall,
                "field_report": field_report,
                "documents_compared": len(per_document_outcomes),
                "documents_skipped": skipped,
                "documents_failed": failed,
                "per_document": per_document_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    click.echo(f"\n📑 Отчёт: {report_path}\n")


if __name__ == "__main__":
    main()
