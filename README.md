# requisites_extractor

Сервис для извлечения реквизитов организации из DOCX, PDF и изображений с помощью комбинации routing, OCR, нормализации, LLM, fallback-regex и валидации.[file:232]

## Что умеет проект

- Обрабатывает DOCX, DOC (через LibreOffice), ODT, PDF с текстовым слоем, PDF-сканы и изображения.[file:232]
- Использует pipeline: routing → extraction → normalization → LLM → fallback regex → validation → export.[file:232]
- Поддерживает экспорт результата в JSON, XLSX и заполненный DOCX-шаблон.[file:232]
- Поднимает Flask-приложение с health endpoint `/api/health`.[file:231][file:232]

## Текущее состояние

- Docker runtime настроен: контейнер собирается, сервис поднимается на `localhost:5000`, healthcheck проходит.[file:231][web:154]
- Flask API отвечает по `/api/health` JSON-ответом вида `{"status": "ok", "version": "1.0.0"}`.[file:231][web:154]
- Интеграция с Ollama по схеме «Ollama на хосте, приложение в Docker» зависит от сетевых настроек WSL/Windows (host.docker.internal/172.17.0.1). Сейчас приложение работает, но доступ к Ollama из контейнера требует дополнительной настройки firewall/сетей.[file:231][web:208][web:212]

## Архитектура

Основной pipeline проекта:[file:232]

1. Routing документа по типу входа (DOCX / DOC / ODT / PDF-text / PDF-scan / image / unsupported).[file:232]
2. Извлечение текста через нативные экстракторы или OCR (бэкенд по `OCR_BACKEND`, по умолчанию Tesseract; страницы PDF рендерит Poppler, без него — pypdfium2). Для фото и сканов делаются дополнительные проходы OCR (другие режимы сегментации) — только для поиска чисел.
3. Нормализация текста и числовых реквизитов.[file:231][file:232]
4. Извлечение через LLM-провайдера (`mock`, `openai`, `ollama`, `yandex`). Сбой LLM не останавливает обработку — остаются regex и контрольные суммы.[file:232]
5. Fallback regex для критичных реквизитов (ИНН, КПП, ОГРН, БИК, счета, контакты).[file:232]
5a. Текстовые поля (наименования, адреса, банк, руководитель) берутся из ответа LLM; regex только заполняет пустые. Краткое ФИО строится программой из полного.
5b. Числовые реквизиты по кандидатам (`number_candidates_service`): из текста собираются все подходящие числа, остаются прошедшие контрольную сумму, выбирается стоящее у нужной метки; счета сверяются с БИК по контрольному ключу ЦБ. Значение LLM — только подсказка при равных кандидатах.
6. Валидация и кросс-проверка реквизитов с контрольными суммами (включая ключ р/с и к/с по БИК).[file:232]
7. Экспорт результата в JSON/XLSX/шаблон DOCX.[file:232]

## Быстрый старт (локально)

### Требования

- Python 3.11+[file:231][file:232]
- Tesseract OCR (с русским языком)
- Poppler utils для PDF-сканов — необязательно: без него страницы рендерятся через pypdfium2[file:231][file:232]
- LibreOffice — только для `.doc` (путь можно задать в `LIBREOFFICE_PATH`)

### Установка

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# или Linux/macOS
source .venv/bin/activate

pip install -r requirements/dev.txt
```

### Запуск dev-сервера

```bash
python scripts/run_dev.py
```

### Проверка health endpoint

```bash
curl http://localhost:5000/api/health
```

Ожидаемый ответ:

```json
{"status": "ok", "version": "1.0.0"}
```

## Запуск через Docker

### Сборка и запуск

```bash
docker compose up --build
```

Проверка:

```bash
curl http://localhost:5000/api/health
```

Контейнерный healthcheck настроен на `/api/health`, при успешном запуске контейнер переходит в состояние `healthy`.[file:231][web:154]

### Ollama

- **Вариант A** — Ollama установлен на хостовой машине, приложение в Docker обращается к `http://host.docker.internal:11434`. Это текущий приоритетный сценарий, не раздувает образ, но в WSL/Windows может упираться в firewall/маршрутизацию.[file:231][web:208][web:212]
- **Вариант B** — отдельный сервис `ollama` в `docker-compose.yml` для полностью воспроизводимого стенда (пока в планах).[file:231]
- **Вариант C** — `LLM_PROVIDER=mock` для тестов и CI, без зависимости от внешнего LLM.[file:231]

## Переменные окружения

Минимальный набор задаётся в `.env` (см. `.env.example`):[file:231][file:232]

- `FLASK_ENV` — режим работы Flask.
- `LLM_PROVIDER` — `mock` / `openai` / `ollama` / `yandex`.
- `OPENAI_API_KEY` — при использовании OpenAI.
- `OLLAMA_BASE_URL` — базовый URL Ollama.
- `OCR_BACKEND` — `tesseract` / `easyocr` / `yandex` (Yandex Vision OCR; при сбое — Tesseract).
- `YANDEX_API_KEY`, `YANDEX_FOLDER_ID` — доступ к Yandex AI Studio (YandexGPT и Vision OCR); `YANDEX_GPT_MODEL` (по умолчанию `yandexgpt/latest`), `YANDEX_DATA_LOGGING=false` — запросы не сохраняются на стороне Yandex.
- `OCR_EXTRA_PASSES` — дополнительные проходы OCR для поиска чисел (`true` по умолчанию; `false` — быстрее, но хуже на фото).
- `LIBREOFFICE_PATH` — путь к `soffice` для `.doc` (пусто — автопоиск).
- `PROMPT_VERSION` — `v1` для локальных моделей, `v4` для облачных (дословное копирование текстовых полей).
- `OCR_MIN_CHARS_PER_PAGE` — PDF с меньшим числом символов на страницу считается сканом (по умолчанию 200).
- `POPPLER_PATH`, `TESSERACT_CMD` — пути к Poppler и Tesseract на Windows.
- Ограничения размеров входных файлов.

## Тесты

CI (GitHub Actions): `ruff` и `pytest` на Python 3.12/3.13 при каждом PR, без внешних сервисов (`LLM_PROVIDER=mock`, `OCR_BACKEND=tesseract`).

Проект содержит тесты для:[file:231][file:232]

- валидаторов (ИНН, КПП, ОГРН, БИК, счета),
- fallback regex,
- normalization и routing,
- docx/pdf_text extractor’ов,
- полного pipeline на mock LLM.

Запуск:

```bash
pytest
```

## Замер точности

`scripts/evaluate.py` прогоняет pipeline по папке документов и сравнивает результат с эталоном.

```bash
# 1. Создать/дополнить шаблон эталона FOLDER/ground_truth.json (все поля null)
python scripts/evaluate.py requisites --init
# 2. Заполнить эталон: строка — правильное значение, "" — поля в документе нет, null — не проверено
# 3. Замер (по умолчанию LLM_PROVIDER из .env; --provider mock — только regex и контрольные суммы)
python scripts/evaluate.py requisites --provider mock --label regex_only
# облако: YandexGPT + Yandex Vision OCR
python scripts/evaluate.py requisites --provider yandex --ocr yandex --label yandex
```

Печатаются только метрики: точность по полям и по типам документов, а без эталона — доля полей, заполненных и прошедших валидацию. Значения реквизитов выводятся только с флагом `--show-errors`. Отчёт сохраняется в `exports/eval_*.json`.

Папка `requisites/` с реальными документами контрагентов исключена из git (персональные данные).

## Review-форма

Главный интерфейс: `python scripts/run_web.py` → `http://127.0.0.1:5000/`.

1. Загрузка документа (PDF, DOCX, DOC, ODT, фото).
2. Форма с 16 полями: распознанное значение, источник (LLM / regex / контрольная сумма), ошибка или предупреждение у каждого поля. Невалидное значение показывается как есть, чтобы его можно было исправить.
3. «Сформировать DOCX» — заполненный `shablon.docx` отдаётся из памяти, на диск не сохраняется. Жёсткая ошибка (например, неверная контрольная сумма ИНН) блокирует генерацию, пока не поставлена галочка подтверждения; предупреждения не блокируют.

Интерфейс работает без интернета: Bootstrap лежит в `app/static/vendor/`.

## Web UI и API тесты

В `app/static/test_ui.html` есть простой тестовый UI для ручной проверки:[file:232]

- `GET /api/health`
- `POST /api/extract` (загрузка файла)
- `GET /api/download/...` (скачивание результата)

Он собирается как статический файл и не требует отдельной сборки фронтенда.

## План развития (high-level)

- Усиление валидаторов и fallback regex (validator hardening).[file:231][file:232]
- Улучшение OCR: структурный OCR, разные backends.[file:231][file:232]
- Расширение схемы результата (`extracted_by`, `review_reasons`, `fill_rate`).[file:231][file:232]
- CI/CD на базе GitHub Actions (lint + tests).[file:231][file:232]
- Документация и CONTRIBUTING для новых разработчиков.[file:232]