# requisites_extractor

[![CI](https://github.com/ippolkovnikovas-hash/requisites_extractors/actions/workflows/ci.yml/badge.svg)](https://github.com/ippolkovnikovas-hash/requisites_extractors/actions/workflows/ci.yml)

Локальное приложение для извлечения реквизитов организации из документов
(PDF, DOCX, изображения) и заполнения ими договорного шаблона `shablon.docx`.

Работает целиком на твоей машине: OCR локальный, LLM локальная (Ollama),
никаких внешних сервисов.

---

## Приватность

Это не «фича», а жёсткое ограничение проекта:

- **Реквизиты никогда не покидают машину.** Внешние API и облачные
  LLM-провайдеры исключены из кода и зависимостей.
- **LLM — только локальный Ollama** (`http://localhost:11434`) или `mock`
  (тесты/CI). Других провайдеров в проекте нет.
- Приложение слушает `127.0.0.1` и не требует интернета для работы.

Правила целиком — в [`CLAUDE.md`](CLAUDE.md).

---

## Основной сценарий

```
документ  →  распознавание  →  review-форма  →  «Сформировать DOCX»
 PDF/DOCX/JPG    OCR + LLM +      ручная            заполненный
                 regex            проверка          shablon.docx
```

Смысл в шаге «review-форма»: распознавание не бывает идеальным, поэтому
результат не уходит в документ автоматически. Ты видишь каждое из 16 полей,
рядом с полем — предупреждение или ошибка валидации, и правишь то, что нужно,
перед генерацией.

Готовый документ отдаётся из памяти: он не сохраняется ни в `exports/`, ни где-либо
ещё на диске.

Жёсткая ошибка валидации блокирует генерацию до тех пор, пока вы явно не
подтвердите её галочкой. Предупреждение не блокирует никогда. Незаполненное
поле — тоже: «пусто» и «введено неверно» это разные состояния.

---

## Что уже работает

- **Маршрутизация форматов** — DOCX, PDF с текстовым слоем, PDF-скан,
  изображения (JPG/PNG/TIFF).
- **Извлечение текста** — `python-docx`, `pdfplumber`, Tesseract OCR с
  построчной сборкой через `image_to_data` и предобработкой изображений.
- **LLM-извлечение** — локальная Ollama, три версии промпта (`v1` базовый,
  `v2` chain-of-thought для договоров, `v3` для малых моделей).
- **Fallback regex** — контекстный поиск ИНН/КПП/ОГРН/БИК/р.с/к.с, разбор
  карточки контрагента, извлечение ФИО руководителя с нормализацией порядка
  слов и краткой формой. Результаты LLM и regex объединяются с пометкой
  источника (`extracted_by`).
- **Валидация** — контрольные суммы ИНН и ОГРН, форматные проверки КПП, БИК,
  счетов, кросс-проверка БИК ↔ корр. счёт.
- **Экспорт** — JSON, XLSX и заполнение `shablon.docx`.
- **Review-форма** — все 16 полей с подписями, ошибками и предупреждениями
  рядом с полем, пометкой источника значения (LLM или regex) и генерацией
  заполненного DOCX прямо из формы.
- **CLI** — обработка одного файла, пакетная обработка папки с отчётом,
  проверка отдельного реквизита.
- **REST API** — загрузка, получение результата, скачивание.

Честный список того, что **не** доделано, — в [ROADMAP.md](ROADMAP.md), §1.2.

---

## Требования

- **Python 3.13+** (проверено на 3.13 и 3.14)
- **Tesseract OCR** с русским языковым пакетом — для сканов и изображений
- **Poppler** — для растеризации PDF-сканов
- **Ollama** с локальной моделью — для LLM-извлечения
  (без неё можно работать на `LLM_PROVIDER=mock`, но качество будет никакое)

Интернет нужен только на этапе установки: Bootstrap лежит в репозитории
локально, никаких CDN и внешних запросов при работе нет.

### Установка системных зависимостей (Windows)

```powershell
winget install UB-Mannheim.TesseractOCR
winget install oschwartz10612.Poppler
winget install Ollama.Ollama
```

Пути к Tesseract и Poppler пропиши в `.env`, если они не в `PATH`.

### Модель для Ollama

```bash
ollama pull qwen2.5:7b-instruct
```

Быстрее, но менее точна на банке/наименованиях/адресах — `qwen2.5:3b`
(замер 05.09.2026 на 15 реальных документах: 62.2% против 57.6% общей
точности в пользу 7b, числовые поля не отличаются, ~63 с/документ против
~10 с).

---

## Установка

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

Linux/macOS:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

EasyOCR вынесен в отдельный extra: он тянет torch (~500 МБ), а по умолчанию
используется Tesseract. Ставьте, только если собираетесь переключить
`OCR_BACKEND=easyocr`:

```bash
pip install -e ".[easyocr]"
```

Затем отредактируй `.env` под свою машину. `.env` в Git не попадает.

---

## Запуск

```bash
python scripts/run_app.py
```

Приложение поднимается на `http://127.0.0.1:5000/` и само открывает браузер.
Остановить — `Ctrl+C`.

Одна команда поднимает и веб-интерфейс (`/`), и REST API (`/api`). Слушается
только localhost: наружу в сеть ничего не торчит.

```bash
python scripts/run_app.py --no-browser      # не открывать браузер
python scripts/run_app.py --port 8000       # другой порт
```

После `pip install -e .` доступны короткие команды:

```bash
requisites-extractor      # веб-приложение
reqextract process файл.pdf   # CLI
```

> `scripts/run_dev.py` и `scripts/run_web.py` оставлены как совместимые
> обёртки над `run_app.py` и будут удалены.

### CLI

```bash
# Один файл
python scripts/run_cli.py process путь/к/документу.pdf --show-result

# С другой версией промпта
python scripts/run_cli.py process документ.pdf --prompt-version v2

# Вся папка
python scripts/run_cli.py batch путь/к/папке -e pdf -e docx

# Папка с отчётом CSV/JSON
python scripts/batch_process.py путь/к/папке -e pdf -e docx

# Проверить одно значение
python scripts/run_cli.py validate 7744012347 --type inn

# Текущие настройки
python scripts/run_cli.py info
```

---

## REST API

| Метод | Путь | Назначение |
|-------|------|-----------|
| `GET` | `/api/health` | Проверка живости: `{"status": "ok", "version": "1.0.0"}` |
| `POST` | `/api/extract` | Загрузка файла (`multipart/form-data`, поле `file`) |
| `GET` | `/api/result/<document_id>` | Результат обработки |
| `GET` | `/api/download/<document_id>/<fmt>` | Скачивание: `json`, `xlsx`, `docx` |
| `GET` | `/test` | Статическая страница для ручной проверки API |

Веб-интерфейс: `GET /` — загрузка, `POST /upload` — обработка и review-форма,
`POST /generate` — заполненный DOCX.

Ошибки возвращаются единым форматом: `{"error": ..., "code": ..., "details": ...}`.

```bash
curl -F "file=@документ.pdf" http://127.0.0.1:5000/api/extract
```

---

## Переменные окружения

Полный список с комментариями — в [`.env.example`](.env.example).

| Переменная | По умолчанию | Назначение |
|------------|--------------|-----------|
| `LLM_PROVIDER` | `mock` | `ollama` или `mock`. Других значений нет |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Локальный endpoint Ollama |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Имя модели |
| `PROMPT_VERSION` | `v1` | `v1`, `v2` или `v3` |
| `LLM_TIMEOUT_SECONDS` | `120.0` | Таймаут запроса к LLM |
| `TESSERACT_CMD` | из `PATH` | Путь к `tesseract` |
| `POPPLER_PATH` | из `PATH` | Путь к Poppler |
| `OCR_BACKEND` | `tesseract` | `tesseract` или `easyocr` |
| `OCR_PROMPT_VERSION` | `image` | Профиль промпта для распознанного текста |
| `MAX_UPLOAD_SIZE_MB` | `20` | Лимит размера файла |
| `PERSIST_ARTIFACTS` | `false` | Сохранять ли результаты обработки на диск |
| `FLASK_HOST` / `FLASK_PORT` | `127.0.0.1` / `5000` | Адрес веб-сервера |
| `FLASK_SECRET_KEY` | — | Обязательно поменять |

---

## Архитектура

```
app/
├── api/          REST-эндпоинты (health, upload/extract/download)
├── core/         константы, enum'ы, исключения, утилиты
├── exporters/    JSON, XLSX, заполнение DOCX-шаблона
├── extractors/   DOCX, PDF-текст, PDF-OCR, изображения
├── llm/          базовый интерфейс, mock, ollama, промпты
├── ocr/          интерфейс OCR-бэкенда, Tesseract, EasyOCR
├── schemas/      pydantic-модели (документ, реквизиты, валидация)
├── services/     routing, извлечение текста, нормализация,
│                 fallback regex, валидация, оркестратор pipeline
├── validators/   ИНН, КПП, ОГРН, БИК, счета, кросс-проверки
└── web/          Flask-роуты и шаблоны интерфейса
```

Порядок обработки в `services/pipeline_service.py`:

1. **DocumentInput** — файл, sha256, расширение, MIME
2. **Routing** — определение типа: DOCX / PDF-текст / PDF-скан / изображение
3. **Extraction** — извлечение текста нужным экстрактором
4. **Normalization** — очистка текста перед LLM
5. **LLM** — структурированный JSON от Ollama
6. **Fallback regex + merge** — добор полей регулярками, слияние с пометкой источника
7. **Validation** — контрольные суммы, форматы, кросс-проверки
8. **Export** — JSON, XLSX, заполненный DOCX
9. **PipelineResult** — итог с `fill_rate`, `needs_review`, `warnings`

---

## Шаблон DOCX

`shablon.docx` в корне проекта. Плейсхолдеры — имена в **одинарных кавычках**,
например `'FULL_ORG_NAME'`, `'INN'`. Работают и в обычных параграфах, и в
ячейках таблиц; разбиение плейсхолдера по runs обрабатывается корректно.

16 полей: `FULL_ORG_NAME`, `ORG_NAME`, `LEGAL_ADDRES`, `POST_ADDRES`, `OGRN`,
`INN`, `KPP`, `BANK_NAME`, `RS`, `KS`, `BIK`, `CEO_POSITION`, `CEO_FIO_FULL`,
`CEO_FIO`, `TEL`, `E-MAIL`.

Чтобы использовать свой шаблон, замени файл, сохранив имена плейсхолдеров.

---

## Разработка

Порядок работы — TDD: сначала тест, затем реализация, затем прогон.

```bash
pytest                                          # весь набор с coverage
pytest --no-cov tests/test_validators_inn.py    # отдельный модуль
ruff check app/ scripts/ tests/
black --check app/ scripts/ tests/
```

Все три проверки должны проходить чисто — ровно они и запускаются в CI
(`.github/workflows/ci.yml`) на Python 3.13 и 3.14, с `LLM_PROVIDER=mock`.

Часть тестов написана **вперёд реализации** — они падают с `ImportError`, и это
ожидаемое состояние, а не поломка. Такие тесты задают контракт для эпиков Э3–Э7
из [ROADMAP.md](ROADMAP.md).

Порог coverage и список исключений (`omit` в `pyproject.toml`) снижать нельзя —
только сокращать `omit` и поднимать порог.

---

## Ограничения

- Качество извлечения не измерялось на реальных документах: `fill_rate`
  проверялся только на синтетических фикстурах.
- Версии зависимостей не закреплены — сборка может сломаться от обновления
  внешнего пакета.
- Нет `docs/architecture.md` и `CONTRIBUTING.md`.

## Файлы на диске

По умолчанию обработка **не оставляет следов**: ни распознанного текста в
`processed/`, ни результатов в `exports/`. Веб-форма отдаёт готовый DOCX из
памяти, REST-скачивание собирает запрошенный формат на лету.

Сохранение включают там, где оно и нужно, — в CLI:

```bash
python scripts/run_cli.py process документ.pdf            # сохранит отчёты
python scripts/run_cli.py process документ.pdf --no-save  # ничего не сохранит
python scripts/batch_process.py папка/                    # сохранит отчёты
```

Глобально поведение задаётся `PERSIST_ARTIFACTS` в `.env` (по умолчанию `false`).

Docker из проекта убран сознательно: для локального десктопного приложения он
добавлял установку Docker Desktop и проблемы с доступом к Ollama на хосте,
не решая ни одной реальной задачи.

---

## Документация

- [`docs/architecture.md`](docs/architecture.md) — устройство приложения: слои,
  pipeline, контракт валидации, точки расширения
- [`docs/extraction-notes.md`](docs/extraction-notes.md) — как ведут себя слои
  извлечения, где ломаются, что уже находили
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — порядок работы: TDD, проверки, коммиты
- [`CLAUDE.md`](CLAUDE.md) — правила проекта: приватность, валидация, работа с Git
- [`ROADMAP.md`](ROADMAP.md) — фактическое состояние кода и план работ

Историческое: [`docs/plan-14.06.26.md`](docs/plan-14.06.26.md) и
[`docs/plan-21.06.26.txt`](docs/plan-21.06.26.txt) — исходные планы, из которых
вырос текущий ROADMAP.
