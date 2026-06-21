# requisites_extractor

Сервис для извлечения реквизитов организации из DOCX, PDF и изображений с помощью комбинации routing, OCR, нормализации, LLM, fallback-regex и валидации.[file:232]

## Что умеет проект

- Обрабатывает DOCX, PDF с текстовым слоем, PDF-сканы и изображения.[file:232]
- Использует pipeline: routing → extraction → normalization → LLM → fallback regex → validation → export.[file:232]
- Поддерживает экспорт результата в JSON, XLSX и заполненный DOCX-шаблон.[file:232]
- Поднимает Flask-приложение с health endpoint `/api/health`.[file:231][file:232]

## Текущее состояние

- Docker runtime настроен: контейнер собирается, сервис поднимается на `localhost:5000`, healthcheck проходит.[file:231][web:154]
- Flask API отвечает по `/api/health` JSON-ответом вида `{"status": "ok", "version": "1.0.0"}`.[file:231][web:154]
- Интеграция с Ollama по схеме «Ollama на хосте, приложение в Docker» зависит от сетевых настроек WSL/Windows (host.docker.internal/172.17.0.1). Сейчас приложение работает, но доступ к Ollama из контейнера требует дополнительной настройки firewall/сетей.[file:231][web:208][web:212]

## Архитектура

Основной pipeline проекта:[file:232]

1. Routing документа по типу входа (DOCX / PDF-text / PDF-scan / image / unsupported).[file:232]
2. Извлечение текста через нативные экстракторы или OCR (Tesseract + Poppler).[file:232][file:231]
3. Нормализация текста и числовых реквизитов.[file:231][file:232]
4. Извлечение через LLM-провайдера (`mock`, `openai`, `ollama`).[file:232]
5. Fallback regex для критичных реквизитов (ИНН, КПП, ОГРН, БИК, счета, контакты).[file:232]
6. Валидация и кросс-проверка реквизитов с контрольными суммами.[file:232]
7. Экспорт результата в JSON/XLSX/шаблон DOCX.[file:232]

## Быстрый старт (локально)

### Требования

- Python 3.11+[file:231][file:232]
- Tesseract OCR (с русским языком)
- Poppler utils для работы с PDF-сканами[file:231][file:232]

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
- `LLM_PROVIDER` — `mock` / `openai` / `ollama`.
- `OPENAI_API_KEY` — при использовании OpenAI.
- `OLLAMA_BASE_URL` — базовый URL Ollama.
- Настройки OCR backend’ов.
- Ограничения размеров входных файлов.

## Тесты

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