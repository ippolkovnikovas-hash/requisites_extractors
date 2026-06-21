# ROADMAP — requisites_extractor

Документ отражает текущий статус проекта и дальнейший план, основанный на твоём плане от 21.06.2026 и старом ROADMAP.[file:231][file:232]

## Текущее состояние

**Что уже работает:**[file:232]

- Полный pipeline: routing → extraction → normalization → LLM → fallback regex → validation → export.[file:232]
- Маршрутизация форматов: DOCX / PDF-text / PDF-scan / image / unsupported.[file:232]
- Экстракторы: docx_extractor, pdf_text_extractor, pdf_ocr_extractor, image_ocr_extractor.[file:232]
- Валидаторы с контрольными суммами: ИНН, КПП, ОГРН, БИК, счета + кросс-проверка БИК↔корр.счёт.[file:232]
- LLM-слой: mock, openai, ollama, версионирование промптов.[file:232]
- Fallback regex-слой и merge LLM+regex с `extracted_by`.[file:232]
- Экспортёры: JSON, XLSX, заполнение шаблона DOCX.[file:232]
- Web UI на Flask и тестовый статический UI для API.[file:232]
- Docker runtime (Python 3.11-slim, Tesseract, Poppler, healthcheck, compose).[file:231][web:154]

**Главные долги:**[file:232]

- Укрепление валидаторов и fallback regex.
- Улучшение OCR (структурный OCR, backends).[file:231][file:232]
- Расширение схемы результата (`fill_rate`, `review_reasons`).[file:231][file:232]
- CI/CD на GitHub Actions.[file:231][file:232]
- Полная документация (README, architecture, CONTRIBUTING).[file:232]

## Эпики и порядок работ

### 1. Гигиена репозитория (Ч.1)

- Очистка мусорных файлов и временных скриптов.[file:231][file:232]
- Настройка `.gitignore` (env, venv, exports, logs, кэш).[file:231][file:232]
- `.env` убрать из git, `.env.example` — добавить.[file:231][file:232]
- Очистка `exports/` в git, оставить только `.gitkeep`.[file:231][file:232]

**Статус:** выполнено частично (cleanup и exports уже в истории).[file:231][file:232]

### 2. Тесты (Ч.3)

- Unit-тесты валидаторов.[file:231][file:232]
- Тесты regex-слоя.[file:231][file:232]
- Тесты normalization и routing.[file:231][file:232]
- Интеграционные тесты pipeline на mock LLM.[file:231][file:232]

**Статус:** тестовый фундамент добавлен (validators, routing, extractors, pipeline), но пороги coverage и расширение тестов ещё впереди.[file:231][file:232]

### 3. Docker и окружения (Ч.8)

- Dockerfile с Tesseract, Poppler, libmagic, non-root user.[file:231]
- `docker-compose.yml` для сервиса `app` (и позже — опциональный `ollama`).[file:231]
- Healthcheck на `/api/health` и документация по запуску.[file:231][web:154]

**Статус:** базовый runtime и healthcheck реализованы и задокументированы, интеграция с Ollama в варианте A зависит от сети WSL/Windows.[file:231][web:208][web:212]

### 4. Качество извлечения (Ч.5)

Разбито на 7 подэтапов:[file:231][file:232]

1. **Validator hardening** — `review_reasons`, защита от ОКПО/ОКТМО/ОКВЭД в поле ОГРН, очистка невалидных полей.[file:231][file:232]
2. **Усиление fallback regex** — контекстный поиск БИК/рс/кс, канонизация номеров.[file:231][file:232]
3. **Split промптов** — отдельные профили для текстовых и image/table сценариев.[file:231][file:232]
4. **Нормализация OCR-текста** — `normalize_ocr_text`, `normalize_requisite_numbers`, `split_classifiers_block`.[file:231][file:232]
5. **Структурный OCR** — `image_to_data`, группировка строк, key-value-extraction.[file:231][file:232]
6. **OCR backends** — интерфейс + Tesseract/EasyOCR backend’ы.[file:231][file:232]
7. **Расширение схемы результата** — `extracted_by`, `review_reasons`, `fill_rate`.[file:231][file:232]

**Статус:** ключевой продуктовый эпик, пока в планах; кодовая база и тесты подготовлены к этому этапу.[file:231][file:232]

### 5. REST API и Web UI (Ч.6)

- `app/main.py`, `app/dependencies.py`, API-роуты `health`, `upload`, `download`.[file:231][file:232]
- Единый формат ошибок.[file:231][file:232]
- Тесты API.[file:231][file:232]
- Статический UI в `app/static/test_ui.html` для ручной проверки.[file:232]

**Статус:** первый foundation-коммит уже сделан, требуется полировка и тесты.[file:231][file:232]

### 6. CLI и batch (Ч.7)

- Ревизия `scripts/run_cli.py`.[file:231]
- `scripts/run_dev.py` и `scripts/batch_process.py`.[file:231][file:232]
- Единые entry points через `pyproject.toml`.[file:231][file:232]

**Статус:** базовые скрипты уже существуют, дальше — приведение к единому стандарту и тесты.[file:231][file:232]

### 7. CI/CD (Ч.4)

- `.github/workflows/ci.yml` (Python 3.11/3.12, ruff, black, pytest).[file:231][file:232]
- Бейджи статуса в README.[file:232]
- (Опционально) pre-commit и Dependabot.[file:231][file:232]

**Статус:** запланировано, ещё не реализовано.[file:231][file:232]

### 8. Документация и наблюдаемость (Ч.9)

- Актуальный README.[file:232]
- `docs/architecture.md` и `docs/extraction-notes.md`.[file:231][file:232]
- CONTRIBUTING.[file:232]
- Структурное логирование и метрики качества.[file:232]

**Статус:** README и новый ROADMAP добавляются сейчас; остальная документация и логирование — следующий шаг.[file:231][file:232]

## Краткий порядок на ближайшее время

1. Завершить документацию первой линии (README, ROADMAP, basic docs). [file:231][file:232]
2. Усилить тесты и покрытие для валидаторов и pipeline. [file:231][file:232]
3. Включить CI на GitHub Actions. [file:231][file:232]
4. Двигаться по шагам Ч.5 (качество извлечения) отдельными коммитами.[file:231][file:232]