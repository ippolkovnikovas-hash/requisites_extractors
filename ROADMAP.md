# ROADMAP — requisites_extractor

Документ переписан 23.08.2026 после построчной сверки `CLAUDE.md`, `README.md`,
старого `ROADMAP.md` и `docs/plan-21.06.26.txt` с фактическим кодом на коммите
`2115012`. Всё, что ниже помечено как «работает», проверено чтением кода и
прогоном `pytest`; всё, что помечено как «нет» — отсутствует в репозитории.

Предыдущая версия документа описывала как готовое многое из того, чего в коде
нет (см. §2). Здесь такого нет: статусы отражают код, а не намерения.

---

## 0. Продуктовая рамка и зафиксированные решения

Решения приняты 23.08.2026 и являются входными условиями для всего плана ниже.

| # | Решение |
|---|---------|
| Р1 | Это **локальное однопользовательское приложение**, а не сервис. Всё проектируется под запуск на машине пользователя, без сети наружу. |
| Р2 | Главный интерфейс — **web review-форма**: загрузка → правка распознанных полей → `POST /generate` → DOCX. REST API (`/api/*`) остаётся вспомогательным слоем для CLI/batch/интеграций, но не ведёт разработку. |
| Р3 | **OpenAI удаляется полностью** — код, зависимость, настройки, упоминания в документации. Остаются только `ollama` (локальный endpoint) и `mock` (тесты/CI). |
| Р4 | **Сохранение промежуточных артефактов на диск становится опциональным.** По умолчанию pipeline не пишет `processed/*_raw.txt`, `processed/*_normalized.txt` и `exports/*` — всё в памяти. Сохранение включается явным флагом для CLI и batch, где оно действительно нужно. |
| Р5 | **`omit` в coverage сокращается поэтапно**, а не расширяется. Порядок: сначала `validators/` и `core/` (цель ≥90%), затем `services/` и `web/`. Порог `--cov-fail-under` поднимается по мере готовности и не опускается. |
| Р6 | **Docker удалён из проекта.** Для десктопного приложения он требовал установки Docker Desktop и упирался в доступ к Ollama на хосте (firewall/сети WSL), не решая ни одной реальной задачи. CI будет собираться на голых GitHub-раннерах с `apt install tesseract-ocr poppler-utils`. |
| Р7 | **Целевой формат — локальный сервер + браузер:** запуск одной командой или ярлыком, Flask на `127.0.0.1`, автооткрытие браузера. Упаковка в `.exe` и нативное окно не делаются (см. §5). |
| Р8 | **Python 3.13+** — floor 3.13 (текущий `.venv`), поддерживается и 3.14. Проверено: весь стек, включая `torch`/`easyocr`, резолвится на обеих версиях (`torch 2.13.0` публикует `cp314`-колёса). |

---

## 1. Фактическое состояние кода

### 1.1. Что действительно работает

- **Pipeline** (`app/services/pipeline_service.py`) — сквозной проход
  routing → extraction → normalization → LLM → fallback regex → merge →
  validation → export. Оркестратор целостный, логирование по шагам есть.
- **Routing** (`routing_service.py`) — DOCX / PDF-text / PDF-scan / image /
  unsupported, с определением наличия текстового слоя в PDF.
- **Экстракторы** — `docx_extractor`, `pdf_text_extractor` (pdfplumber),
  `pdf_ocr_extractor` (pdf2image + Tesseract), `image_ocr_extractor`
  (предобработка PIL + Tesseract).
- **Структурный OCR** — `TesseractBackend.image_to_lines()` уже использует
  `image_to_data(Output.DICT)` с группировкой по `block_num`/`line_num`.
  Оба OCR-экстрактора им пользуются.
- **Fallback regex** (`fallback_regex_service.py`, ~660 строк) — самый
  проработанный модуль: контекстный поиск ИНН/КПП/ОГРН/БИК/рс/кс, разбор
  карточки контрагента, извлечение ФИО с нормализацией порядка и краткой формы,
  `merge_llm_and_fallback()` с `extracted_by`.
- **LLM-слой** — `base.py`, `mock_client.py`, `ollama_client.py` (только
  локальные провайдеры), три версионированных промпта (`v1`, `v2`, `v3`) с
  `get_prompt()`/`list_versions()`.
- **Экспортёры** — `json_exporter`, `xlsx_exporter`, `docx_exporter.fill_template()`
  (замена плейсхолдеров `'ALIAS'` в параграфах и таблицах, с учётом разбиения по runs).
- **REST API** — `GET /api/health`, `POST /api/extract`, `GET /api/result/<id>`,
  `GET /api/download/<id>/<fmt>`, единый формат ошибок `{error, code, details}`.
- **CLI** — `run_cli.py` (`process`, `batch`, `validate`, `info`),
  `batch_process.py` с отчётом CSV/JSON.
- **Тестовый фундамент** — 21 тестовый модуль, синтетические фикстуры
  (`sample_requisites.docx/.pdf`, `sample_two_pages.pdf`, `sample_with_table.docx`).

### 1.2. Чего нет, хотя старый ROADMAP/README считали это сделанным

| Заявлено | Факт |
|----------|------|
| «Web UI на Flask» | Есть `app/web/routes.py` с `index`/`upload`/`downloads` и два шаблона, но **review-формы нет**, `_build_review_rows` нет, `POST /generate` нет. `templates/result.html` и `templates/upload.html` — пустые файлы. `app/web/forms.py` — пустой. |
| Единое Flask-приложение | **Две несвязанные фабрики**: `app/main.py:create_app()` регистрирует только API-блюпринты, `app/web/__init__.py:create_app()` — только `web_bp`. Друг о друге не знают, запускаются разными скриптами (`run_dev.py` / `run_web.py`). |
| «Кросс-проверка БИК↔корр.счёт» | `app/validators/cross_field_validator.py` — **пустой файл**. Реально работает `validate_cross_bik_corr()` в `account_validator.py`, и она сравнивает `кс[17:20]` с `БИК[-3:]` — это не методика ЦБ РФ №515 из CLAUDE.md. |
| «Нормализация OCR-текста» (Ч.5.4) | `normalize_ocr_text()`, `normalize_requisite_numbers()`, `split_classifiers_block()` написаны — но **мёртвый код**: `normalize_text()` их не вызывает, никто их не импортирует. |
| «OCR backends с переключением» (Ч.5.6) | `OcrBackend` (ABC), `TesseractBackend`, `EasyOcrBackend` есть, но **фабрики нет**: оба экстрактора жёстко импортируют `TesseractBackend`. `settings.ocr_backend` используется ровно в одном месте — печатается в `run_cli.py info`. Вдобавок `image_to_lines()` объявлен только в Tesseract-бэкенде, но не в ABC — переключение на EasyOCR упадёт. |
| «Расширение схемы результата: `review_reasons`, `fill_rate`» (Ч.5.7) | `fill_rate` и `review_reasons` есть. Схема `FieldValidation` при этом **не соответствует** правилам валидации CLAUDE.md (см. §2). |
| «CI/CD на GitHub Actions» | Каталога `.github/` не существует. |
| «Документация: architecture.md, extraction-notes.md, CONTRIBUTING» | В `docs/` лежат только `plan-21.06.26.txt`, `ROADMAP.pdf` и три `.docx`. Ни одного из трёх заявленных файлов нет. |

### 1.3. Пустые файлы-заглушки

`app/core/utils.py`, `app/validators/cross_field_validator.py`,
`app/validators/__init__.py`, `app/exporters/zip_exporter.py`,
`app/llm/json_schema.py`, `app/schemas/export.py`, `app/extractors/base.py`,
`app/web/forms.py`, `app/web/templates/result.html`, `app/web/templates/upload.html`.

Из них под реализацию нужны: `core/utils.py`, `cross_field_validator.py`,
`web/forms.py`, `templates/result.html`. Остальные — кандидаты на удаление.

### 1.4. Состояние тестов (прогон 23.08.2026)

**Обновлено 23.08.2026 после Э3–Э6.** Из восьми несобиравшихся модулей семь
реализованы и зелёные. Текущее состояние:

- **361 тест проходит**, падений нет.
- Не собирается один модуль — `test_web_routes.py` (`_build_review_rows`,
  `POST /generate`). Это контракт эпика Э7, реализация ещё не написана.

Историческая справка: до Э3 не собирались восемь модулей и падало ~25 тестов —
почти все из-за отсутствия `raw_value` / `normalized_value` / `is_missing` /
`warning` в `FieldValidation`.
- ~~`tests/test_pipeline_service.py:211` содержит захардкоженный абсолютный путь
  со старого места проекта.~~ **Исправлено 23.08.2026** — шаблон копируется в
  `tmp_path`, `test_pipeline_service.py` зелёный целиком (19 тестов).

Тесты, написанные вперёд реализации, задают контракт для §3 и являются
источником истины по ожидаемому поведению — реализация подгоняется под них.

---

## 2. Расхождения кода с обязательными правилами CLAUDE.md

Это не «долги», а нарушения зафиксированных правил проекта. Они закрываются в
первую очередь.

### 2.1. Приватность (раздел «Приватность»)

**Закрыто 23.08.2026** — OpenAI удалён полностью: `app/llm/openai_client.py`,
`openai` из `requirements/base.txt`, ветка провайдера в `_build_llm_client()`,
`openai_*`/`llm_model`/`llm_temperature`/`llm_max_tokens` из `app/config.py`,
`OPENAI_*` (включая сторонний прокси `api.proxyapi.ru`) из `.env.example`,
`LLMProvider.OPENAI` из enum'а, упоминания из README. Добавлены два
регрессионных теста: `test_no_external_llm_provider_in_enum` и
`test_openai_client_module_does_not_exist`.

Остаётся:

| Что | Где |
|-----|-----|
| Bootstrap CSS/JS с `cdn.jsdelivr.net` | `app/web/templates/base.html:7,132` — исходящий сетевой запрос при каждом открытии формы; для локального офлайн-приложения (Р1) недопустимо |
| Серверы слушают `0.0.0.0` | `scripts/run_dev.py`, `scripts/run_web.py` — приложение доступно из локальной сети, хотя `settings.flask_host` по умолчанию `127.0.0.1` и скриптами игнорируется |

### 2.2. Правила валидации

| Правило CLAUDE.md | Факт в коде |
|-------------------|-------------|
| `raw_value` всегда сохраняется и не скрывается | В `FieldValidation` **нет поля `raw_value`** — только `value`, `valid`, `reason` |
| `normalized_value` — прозрачная нормализация | Поля **нет вообще** |
| `is_missing` ≠ `valid=False` | Поля **нет**; `validate_*` на `None` возвращают `valid=False, reason="field is null"` — пустое и невалидное неразличимы |
| `warning` не блокирует генерацию | Поля **нет**; всё сваливается в `errors` |
| Префикс БИК — только warning | `bik_validator.py`: «BIK must start with 04» → **hard error** |
| Префикс счёта — только warning | `account_validator.py`: «must start with 40/30» → **hard error** |
| Контрольный ключ БИК↔счёт (ЦБ РФ №515) — всегда warning | `validate_cross_bik_corr()` попадает в `report.errors` → **блокирует**; и алгоритм не тот (сравнение `кс[17:20]` с `БИК[-3:]` вместо расчёта контрольного ключа по `"0"+БИК[4:6]`) |
| Контрольный ключ для р/с (`БИК[6:9]`) | **Не реализован вообще** |
| Отсутствие необязательного поля — не ошибка | `validation_service.py` добавляет «X отсутствует» в `errors` для всех шести полей |
| КПП: 4 цифры + 2 цифры/буквы + 3 цифры | `kpp_validator.py` требует `isdigit()` — **буквы в позициях 5–6 отвергаются**, хотя они легальны |
| Почтовый индекс необязателен, его отсутствие не warning | Валидатора адреса нет вообще |
| `raw_value` не скрывается от пользователя | `validate_requisites()` делает `setattr(data, field_name, None)` — **затирает** исходное значение при невалидности |

### 2.3. Артефакты и Git

- **`logs/app.log` закоммичен в репозиторий** (656 строк). Реквизитов в нём не
  обнаружено, но правило «не хранить в Git логи» нарушено, и файл продолжает
  расти. `.gitignore` содержит `logs/*.log`, но файл был добавлен до этого.
- В корне лежат мусорные артефакты: `test_download.docx`, `test_result.docx`.
- `.coverage` не покрыт `.gitignore`.
- В `docs/` лежат бинарники (`ROADMAP.pdf`, `README_draft.docx`,
  `action_plan.docx`, `updated_roadmap.docx`) — дубликаты текстовой документации.
- `README.md` и старый `ROADMAP.md` содержат артефакты генерации вида
  `[file:231]`, `[file:232]`, `[web:154]`, `[web:208]` — ссылки в никуда.

### 2.4. Coverage

`pyproject.toml` задаёт `--cov-fail-under=70`, но `omit` исключает
`app/services/*`, `app/extractors/*`, `app/llm/*`, `app/web/*`,
`app/validators/*`, `docx_exporter.py`, `xlsx_exporter.py` и почти весь `core/`.
Под измерением остаются схемы, конфиг и два роут-файла. **Порог фиктивен.**

---

## 3. Эпики

Порядок — приоритетный. Каждый эпик = один или несколько отдельных коммитов.
Внутри эпика — TDD: тест → реализация → прогон.

### Э1. Приватность: удаление OpenAI *(в основном сделано 23.08.2026)*

- [x] Удалён `app/llm/openai_client.py`.
- [x] `openai` убран из `requirements/base.txt`.
- [x] Ветка `LLMProvider.OPENAI` убрана из `_build_llm_client()`.
- [x] `openai_*`, `llm_model`, `llm_temperature`, `llm_max_tokens` убраны из
      `app/config.py` (последние три использовались только OpenAI-клиентом).
- [x] `OPENAI_*` убраны из `.env.example`; файл переписан и дополнен реально
      используемыми переменными.
- [x] `OPENAI` убран из `LLMProvider`.
- [x] Упоминания вычищены из `README.md`; ссылки на `settings.openai_model`
      убраны из `scripts/run_cli.py`.
- [x] Добавлены регрессионные тесты на отсутствие внешнего провайдера.
- [ ] Скачать Bootstrap локально в `app/static/vendor/`, убрать CDN-ссылки из
      `base.html`.
- [ ] Неизвестный `LLM_PROVIDER` → явная ошибка конфигурации вместо тихого
      фолбэка на mock. Сейчас опечатка вроде `olama` молча даёт фейковые
      данные. Требует правки `test_build_llm_unknown_falls_back_to_mock`,
      поэтому вынесено отдельным шагом.

**DoD:** `grep -r "cdn\.\|https://" app/web/templates app/static` не находит
внешних хостов; приложение полностью работает без сети.

### Э2. Гигиена репозитория *(сделано 23.08.2026)*

- [x] Починен `tests/test_pipeline_service.py` — захардкоженный абсолютный путь
      заменён на копирование шаблона в `tmp_path`.
- [x] Удалены `Dockerfile`, `docker-compose.yml`, `.dockerignore` (Р6).
- [x] `logs/app.log` убран из индекса Git (файл остался на диске).
- [x] Удалены `test_download.docx`, `test_result.docx` из корня.
- [x] `.gitignore` переписан: убраны дубликаты (`uploads/`, `processed/`,
      `.idea` шли по два раза), исправлен комментарий с битой кодировкой,
      добавлены `.coverage`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`,
      `htmlcov/`.
- [x] **Исправлен серьёзный дефект `.gitignore`:** правила `*.docx` и `*.pdf`
      не имели исключения для `tests/fixtures/`, поэтому все четыре тестовые
      фикстуры не попадали в репозиторий — на свежем клоне тесты не запускались.
      Добавлены `!tests/fixtures/*.docx` и `!tests/fixtures/*.pdf`.
- [x] Бинарники в `docs/` удалены: `README_draft.docx`, `action_plan.docx`,
      `updated_roadmap.docx` (содержание полностью замещено новыми
      README/ROADMAP) и `ROADMAP.pdf` (606 КБ; текст сохранён в
      `docs/plan-14.06.26.md`).
- [x] Удалены пустые заглушки: `zip_exporter.py`, `json_schema.py`,
      `schemas/export.py`, `extractors/base.py`, `templates/upload.html`.
      Проверено — ни одной ссылки в коде.

**Остаточная мелочь:** `logs/__init__.py` — пустой отслеживаемый файл, который
делает `logs/` импортируемым пакетом. По смыслу должен быть `logs/.gitkeep`.

**DoD:** выполнен — `git ls-files` не содержит логов и мусорных документов,
`pytest` падает только на TDD-заготовках (см. §1.4).

### Э3. Схема валидации: `FieldValidation` v2 *(сделано 23.08.2026)*

Переписать `app/schemas/validation.py::FieldValidation` под контракт CLAUDE.md:

```python
class FieldValidation(BaseModel):
    valid: bool
    is_missing: bool = False
    raw_value: str | None = None
    normalized_value: str | None = None
    reason: str | None = None      # только hard error
    warning: str | None = None     # никогда не блокирует
```

Реализовать `app/core/utils.py` (сейчас пуст) — тесты `tests/test_core_utils.py`
требуют:
- `strip_formatting()` — снятие пробелов/дефисов/переносов, без подмены символов;
- `fold_numeric_confusables()` — однозначные OCR-подмены (`О`→`0`, `I`→`1`, …)
  **только в цифровых позициях**.

**DoD:** выполнен — `tests/test_core_utils.py` зелёный (17 тестов),
`FieldValidation` имеет все четыре новых поля, поле `value` убрано.

Дополнительно в `core/utils.py` добавлен `collapse_whitespace()` — общая
нормализация пробелов для текстовых полей (Э5).

**Найдено при реализации:** в `test_core_utils.py` кейс с en dash был
самопротиворечив — во входной строке `"0445–525225"` десять цифр, а ожидалось
девять. Вход исправлен на `"044–525225"`, смысл проверки (тире снимается)
сохранён.

### Э4. Приведение существующих валидаторов к правилам *(сделано 23.08.2026)*

Переписать под новую схему и правила CLAUDE.md:

- **`inn_validator`** — `is_missing` при пустом; OCR-фолдинг в `normalized_value`;
  остаточный мусор после фолдинга → hard error.
- **`kpp_validator`** — структура **4 цифры + 2 цифры/буквы + 3 цифры**;
  OCR-фолдинг **не применять** в буквенных позициях; контрольной суммы нет.
- **`ogrn_validator`** — `is_missing`, OCR-фолдинг, 13/15 знаков.
- **`bik_validator`** — неверная длина/символы → hard error; **нетипичный
  префикс → warning**, не ошибка.
- **`account_validator`** — то же: длина/символы → hard error, **префикс 40/30 →
  warning**.
- **`cross_field_validator.py`** (сейчас пуст) — реализовать
  `validate_bik_account_consistency()` по методике **ЦБ РФ №515**: для р/с
  контрольная база строится с `БИК[6:9]`, для к/с — с `"0" + БИК[4:6]`.
  Результат — **всегда только `warning`**.
  Старую `validate_cross_bik_corr()` из `account_validator.py` убрать.

**DoD:** выполнен — `test_validators_inn/kpp/ogrn/bik_account`,
`test_cross_field_validator`, `test_core_utils` зелёные (111 тестов).
Контрольный ключ ЦБ РФ № 515 сверен с четырьмя публичными тест-векторами.
`cross_field_validator.py` дополнительно получил `validate_inn_kpp_consistency()`
и `validate_ceo_fio_consistency()`.

### Э5. Новые валидаторы полей *(сделано 23.08.2026)*

По контрактам, уже зафиксированным в тестах:

- **`address_validator`** — общий для `legal_address` и `postal_address`.
  Hard error не бывает никогда; сильные признаки (улица/город/регион) снимают
  warning, слабые (индекс/офис/дом) — нет, кроме связки «дом+номер вместе с
  индексом». Индекс сам по себе необязателен. Без ФИАС/КЛАДР и без сети.
- **`email_validator`**, **`phone_validator`**.
- **Текстовые поля**: `company_name_validator`, `short_name_validator`,
  `bank_name_validator`, `ceo_validator`.

**DoD:** выполнен — `test_validators_address/email/phone/text_fields` зелёные
(165 тестов). Созданы `address_validator`, `email_validator`, `phone_validator`,
`company_name_validator`, `short_name_validator`, `bank_name_validator`,
`ceo_validator`.

### Э6. Переписывание `validation_service` *(сделано 23.08.2026)*

- [x] `ValidationReport` расширен со скольких-то полей до **всех 16**, добавлен
      поток `warnings`.
- [x] Разделены три потока: `errors` (только hard, блокируют `/generate`),
      `warnings` (никогда не блокируют), `is_missing` (не ошибка для
      необязательных полей — обязательными считаются только шесть числовых
      реквизитов).
- [x] Контрольный ключ дописывается в `warning` самого счёта, чтобы в форме он
      оказался рядом с полем.
- [x] `needs_review` поднимается и от ошибок, и от предупреждений.

**Уточнение к §2.2.** Ранее в этом документе значилось, что обнуление
невалидных полей (`setattr(..., None)`) надо убрать. Это неверно: контракт из
`test_validation_service.py` и `test_web_routes.py` требует именно обнуления в
`data` — но исходное значение при этом сохраняется в `FieldValidation.raw_value`
и оттуда показывается в review-форме. Правило CLAUDE.md «`raw_value` не
скрывается от пользователя» соблюдено, а мусор в шаблон не попадает.

**DoD:** выполнен — `test_validation_service.py` зелёный (15 тестов).

### Э7. Review-форма и `POST /generate` *(главный продуктовый эпик, Р2)*

Контракт полностью задан в `tests/test_web_routes.py`.

1. **`_build_review_rows(data, field_results, source_map)`** — 16 строк с
   русскими подписями; для невалидного поля показывается `raw_value`, а не
   обнулённое значение; `warning` и `error` разведены; метка ОГРН/ОГРНИП
   выбирается по длине; в строке отражается источник (`llm` / `regex`).
2. **`GET /` → `POST /upload`** — рендер review-формы вместо текущего
   read-only результата. Задействовать `templates/result.html` (сейчас пуст) и
   `web/forms.py` (сейчас пуст).
3. **`POST /generate`**:
   - hard error без `confirm_invalid` → **422**, форма перерисовывается с
     введёнными значениями;
   - с `confirm_invalid` → DOCX генерируется даже с невалидным значением;
   - пустое поле не блокирует;
   - warning не блокирует;
   - результат отдаётся **из `BytesIO`, ничего не остаётся в `exports/`**;
   - отсутствующий `shablon.docx` → аккуратная ошибка, не 500;
   - без `document_id` — безопасное имя файла.
4. **Слить две фабрики приложений** в одну: `app/main.py:create_app()`
   регистрирует и `web_bp`, и API-блюпринты. `run_dev.py`/`run_web.py` свести к
   одной точке входа.
5. **Десктопный запуск (Р7):** одна команда (и ярлык на неё), биндинг на
   `settings.flask_host` = `127.0.0.1` вместо текущего `0.0.0.0`, автооткрытие
   браузера на стартовой странице, `debug=False` по умолчанию.
   Console script в `pyproject.toml`.

**DoD:** зелёный `test_web_routes.py`; ручная проверка сценария
загрузка → правка → «Сформировать DOCX»; приложение поднимается одной командой
и не слушает внешние интерфейсы.

### Э8. Опциональное сохранение артефактов *(Р4)*

- Добавить настройку (напр. `persist_artifacts: bool = False`).
- По умолчанию pipeline **не пишет** `processed/*_raw.txt`,
  `processed/*_normalized.txt`, `exports/*.json|xlsx|docx`.
- CLI и `batch_process.py` включают сохранение явно — там оно осмысленно.
- REST `GET /api/download/<id>/<fmt>` привести в соответствие: либо генерация
  на лету, либо доступен только при включённом сохранении.

**DoD:** после прогона web-сценария `processed/` и `exports/` пусты; CLI с
флагом по-прежнему складывает отчёты.

### Э9. Coverage *(Р5, шаги 1-2 сделаны 23.08.2026)*

- [x] **Шаг 1-2.** Из `omit` убраны `app/validators/*`, `app/core/*`,
      `app/schemas/validation.py` и `app/services/validation_service.py`
      (общий wildcard `app/services/*` заменён на перечисление). Порог поднят с
      **70 → 78**.

      Фактическое покрытие после Э4–Э6: **80% всего**, из них валидаторы
      91-100%, `validation_service` 97%. Ниже 78% тянут `app/api/*`,
      `app/main.py` и `app/dependencies.py` — все по 0%, они попадут под тесты
      в Э7.
- [ ] **Шаг 3.** После Э7 — убрать `app/web/*` и поднять порог.
- [ ] **Шаг 4.** Далее — оставшиеся `app/services/*`, `app/extractors/*`,
      `app/llm/*`, `app/ocr/*`.

Порог `--cov-fail-under` поднимается вместе с каждым шагом. Расширение `omit` и
снижение порога — только с отдельного явного подтверждения.

### Э10. CI/CD

- `.github/workflows/ci.yml`: matrix **Python 3.13 / 3.14** (Р8), кэш pip,
  `apt install tesseract-ocr tesseract-ocr-rus poppler-utils`,
  затем `ruff` → `black --check` → `pytest` с `LLM_PROVIDER=mock`.
- Бейджи в README.
- Опционально: pre-commit, Dependabot.

**Сделано 23.08.2026:** `pyproject.toml` переведён на 3.13 —
`requires-python = ">=3.13"`, `ruff.target-version = "py313"`,
`black.target-version = ["py313"]`, `mypy.python_version = "3.13"`.

**Заметка:** `easyocr` тянет `torch` (~2 ГБ). В CI это либо долгая установка,
либо повод вынести `easyocr` в optional-extra — решить при написании workflow
(перекликается с Э11.2).

### Э11. Качество извлечения

Остаток исходной Ч.5 — то, что действительно не сделано:

1. **Подключить мёртвый код нормализации** — `normalize_ocr_text()`,
   `normalize_requisite_numbers()`, `split_classifiers_block()` вызвать из
   пути OCR-документов (сейчас не вызывается ничем).
2. **Фабрика OCR-бэкендов** — вынести `image_to_lines()` в `OcrBackend` (ABC),
   реализовать её в `EasyOcrBackend`, добавить выбор по `settings.ocr_backend`,
   убрать жёсткий импорт `TesseractBackend` из обоих экстракторов.
   Решить, оставлять ли тяжёлый `easyocr` в `base.txt` или вынести в extra.
3. **Split промптов** — отдельные профили для текстовых и image/table сценариев
   (сейчас v1/v2/v3 различаются по размеру модели, а не по типу документа).
4. **Защита от ОКПО/ОКТМО/ОКВЭД в поле ОГРН**.
5. **Усиление fallback regex** — по результатам прогона на реальных документах,
   с замером fill_rate до/после.

### Э12. Документация

- `README.md` — переписать: убрать артефакты `[file:NNN]`/`[web:NNN]`, убрать
  OpenAI, описать реальный главный сценарий (review-форма), актуальные
  endpoint'ы и переменные окружения.
- `docs/architecture.md` — схема pipeline и слоёв.
- `docs/extraction-notes.md` — заметки по качеству извлечения.
- `CONTRIBUTING.md` — TDD-порядок, линтеры, формат коммитов.
- Структурное логирование: `document_id`, время по этапам, причина `needs_review`.

---

## 4. Порядок работ

```
Э1 приватность ─┐
Э2 гигиена ─────┴─► Э3 схема ─► Э4 валидаторы ─► Э5 новые валидаторы ─► Э6 сервис
                                                                          │
                                                    Э7 review-форма ◄─────┘
                                                          │
                                       Э8 артефакты ◄─────┴─► Э9 coverage
                                                          │
                                            Э10 CI ─ Э11 качество ─ Э12 доки
```

Э1 и Э2 независимы и делаются первыми — они короткие и снимают нарушения правил.
Э3→Э6 — одна логическая цепочка, порядок жёсткий. Э7 — главный продуктовый
результат, ради него всё остальное. Э9 идёт «прицепом» к Э4/Э6/Э7. Э10–Э12
можно вести параллельно после Э7.

**Ближайший шаг: Э1 + Э2.**

---

## 5. Что решено не делать

- **Внешние LLM-провайдеры** любого вида, включая прокси к OpenAI.
- **Справочники ФИАС/КЛАДР и геокодирование** для проверки адресов — валидатор
  адреса работает только на эвристиках, без сети.
- **Контрольная сумма КПП** — её не существует; проверка только структурная.
- **Обязательность почтового индекса** — его отсутствие не создаёт даже warning.
- **Docker в любом виде** (Р6) — включая «вариант B» с контейнером Ollama в
  compose. Ollama ставится на хост как обычное приложение. Вернуться к вопросу
  только если проект будут разворачивать как сервер для нескольких человек.
- **Упаковка в `.exe`** (PyInstaller и аналоги) и **нативное окно**
  (pywebview/Qt) — при Р7 достаточно локального сервера и браузера. Упаковка
  вдобавок упирается в `easyocr`/`torch` (~2 ГБ) и внешние бинарники Tesseract
  и Poppler.
