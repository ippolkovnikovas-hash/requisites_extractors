"""
CLI для запуска pipeline извлечения реквизитов.

Использование:
  python scripts/run_cli.py process path/to/file.pdf
  python scripts/run_cli.py process path/to/file.docx --prompt-version v2
  python scripts/run_cli.py batch path/to/folder/ --ext pdf docx
  python scripts/run_cli.py validate 7712345678 --type inn

Установка как команды (после pip install -e .):
  reqextract process file.pdf
"""

import sys
from pathlib import Path

# Добавляем корень проекта в sys.path — запуск из любой папки
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import click
from loguru import logger

from app.config import settings
from app.logging_config import setup_logging


# ── Главная группа команд ────────────────────────────────────────────────────

@click.group()
def cli():
    """Requisites Extractor — извлечение реквизитов из документов."""
    setup_logging()
    settings.ensure_dirs()


# ── process: обработка одного файла ─────────────────────────────────────────

@cli.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option("--prompt-version", "-p", default=None,
              help="Версия промпта: v1 (default) или v2 (chain-of-thought)")
@click.option("--no-docx", is_flag=True, default=False,
              help="Пропустить заполнение shablon.docx")
@click.option("--show-result", "-s", is_flag=True, default=False,
              help="Вывести итоговые реквизиты в консоль")
def process(file_path: Path, prompt_version: str | None, no_docx: bool, show_result: bool):
    """Обработать один файл и извлечь реквизиты."""
    import json
    from app.services.pipeline_service import run_pipeline
    from app.core.exceptions import AppException

    # Переопределяем версию промпта если передана
    if prompt_version:
        settings.prompt_version = prompt_version

    # Временно отключаем DOCX-экспорт если нужно
    if no_docx:
        import builtins
        _real_exists = Path.exists
        # патч не нужен — pipeline проверяет exists() сам, просто не кладём шаблон

    click.echo(f"\n📄 Файл:    {file_path.name}")
    click.echo(f"🔧 Промпт:  {settings.prompt_version}")
    _model = settings.ollama_model if settings.llm_provider == "ollama" else settings.openai_model
    click.echo(f"🤖 LLM:     {settings.llm_provider} / {_model}\n")

    try:
        result = run_pipeline(file_path, file_path.name)
    except AppException as e:
        click.secho(f"\n❌ Ошибка: {e.message}", fg="red")
        if e.details:
            click.echo(f"   Детали: {e.details}")
        sys.exit(1)
    except Exception as e:
        click.secho(f"\n❌ Неожиданная ошибка: {e}", fg="red")
        raise

    # --- Вывод результата ---
    status_icon = "⚠️ " if result.needs_review else "✅"
    click.echo("─" * 55)
    click.secho(f"{status_icon} Статус:      {result.status}", fg="yellow" if result.needs_review else "green")
    click.echo(f"📊 Заполнено: {int(result.fill_rate * 100)}%  ({len(result.data.filled_fields())}/16 полей)")
    click.echo(f"🆔 doc_id:    {result.document_id}")
    click.echo("─" * 55)
    click.echo(f"📁 JSON:      {result.json_path}")
    click.echo(f"📊 XLSX:      {result.xlsx_path}")
    if result.docx_path:
        click.echo(f"📝 DOCX:      {result.docx_path}")
    if result.warnings:
        click.secho("\n⚠️  Предупреждения:", fg="yellow")
        for w in result.warnings:
            click.echo(f"   • {w}")
    if result.validation.errors:
        click.secho("\n❌ Ошибки валидации:", fg="red")
        for e in result.validation.errors:
            click.echo(f"   • {e}")

    if show_result:
        click.echo("\n📋 Извлечённые реквизиты:")
        click.echo("─" * 55)
        data = result.data.model_dump()
        for field, value in data.items():
            icon = "✅" if value else "  "
            click.echo(f"  {icon} {field:<25} {value or '—'}")

    click.echo()


# ── batch: обработка папки ───────────────────────────────────────────────────

@cli.command()
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--ext", "-e", multiple=True, default=["pdf", "docx"],
              help="Расширения файлов для обработки (можно несколько: -e pdf -e docx)")
@click.option("--prompt-version", "-p", default=None, help="Версия промпта")
def batch(folder_path: Path, ext: tuple, prompt_version: str | None):
    """Обработать все файлы в папке."""
    from app.services.pipeline_service import run_pipeline
    from app.core.exceptions import AppException

    if prompt_version:
        settings.prompt_version = prompt_version

    extensions = {f".{e.lstrip('.')}" for e in ext}
    files = [f for f in folder_path.iterdir() if f.suffix.lower() in extensions]

    if not files:
        click.secho(f"Файлы с расширениями {extensions} не найдены в {folder_path}", fg="yellow")
        return

    click.echo(f"\n📂 Папка: {folder_path}")
    click.echo(f"📄 Найдено файлов: {len(files)}\n")

    ok, failed, review = 0, 0, 0

    for i, file_path in enumerate(sorted(files), 1):
        click.echo(f"[{i}/{len(files)}] {file_path.name} ... ", nl=False)
        try:
            result = run_pipeline(file_path, file_path.name)
            if result.needs_review:
                click.secho("⚠️  needs_review", fg="yellow")
                review += 1
            else:
                click.secho("✅ done", fg="green")
                ok += 1
        except AppException as e:
            click.secho(f"❌ {e.message}", fg="red")
            failed += 1
        except Exception as e:
            click.secho(f"❌ {e}", fg="red")
            failed += 1

    click.echo("\n" + "─" * 40)
    click.echo(f"✅ Успешно:      {ok}")
    click.echo(f"⚠️  На проверку: {review}")
    click.echo(f"❌ Ошибок:       {failed}")
    click.echo(f"📁 Экспорт:      {settings.exports_folder}\n")


# ── validate: быстрая проверка одного значения ───────────────────────────────

@cli.command()
@click.argument("value")
@click.option("--type", "-t", "field_type",
              type=click.Choice(["inn", "kpp", "ogrn", "bik", "rs", "ks"]),
              required=True,
              help="Тип реквизита для проверки")
def validate(value: str, field_type: str):
    """Проверить одно значение реквизита."""
    from app.validators.inn_validator import validate_inn
    from app.validators.kpp_validator import validate_kpp
    from app.validators.ogrn_validator import validate_ogrn
    from app.validators.bik_validator import validate_bik
    from app.validators.account_validator import validate_account

    validators = {
        "inn":  lambda v: validate_inn(v),
        "kpp":  lambda v: validate_kpp(v),
        "ogrn": lambda v: validate_ogrn(v),
        "bik":  lambda v: validate_bik(v),
        "rs":   lambda v: validate_account(v, "checking"),
        "ks":   lambda v: validate_account(v, "correspondent"),
    }

    result = validators[field_type](value)

    if result.valid:
        click.secho(f"✅ {field_type.upper()} «{value}» — валидно", fg="green")
    else:
        click.secho(f"❌ {field_type.upper()} «{value}» — ошибка: {result.reason}", fg="red")


# ── info: информация о настройках ────────────────────────────────────────────

@cli.command()
def info():
    """Показать текущие настройки (из .env)."""
    provider = settings.llm_provider
    model = settings.ollama_model if provider == "ollama" else settings.openai_model

    click.echo("\n⚙️  Текущие настройки:")
    click.echo("─" * 40)
    click.echo(f"  LLM провайдер:  {provider}")
    click.echo(f"  LLM модель:     {model}")
    click.echo(f"  OCR backend:    {settings.ocr_backend}")
    click.echo(f"  Tesseract:      {settings.tesseract_cmd or 'из PATH'}")
    click.echo(f"  Промпт версия:  {settings.prompt_version}")
    click.echo(f"  Uploads:        {settings.upload_folder}")
    click.echo(f"  Exports:        {settings.exports_folder}")
    click.echo(f"  Max upload:     {settings.max_upload_size_mb} MB")
    click.echo(f"  Allowed ext:    {settings.allowed_extensions}\n")


if __name__ == "__main__":
    cli()