import os
os.makedirs(os.path.expanduser('~/output'), exist_ok=True)

readme = '''# Requisites Extractor

Система автоматического извлечения реквизитов организаций из документов (PDF, DOCX, JPG, PNG) с использованием LLM.

---

## Текущий статус проекта

### ✅ Готово и работает
- Pipeline 9 шагов (ingest → routing → extract → normalize → LLM → parse → validate → export → done)
- Извлечение текста из DOCX (`python-docx`)
- Извлечение текста из цифровых PDF (`pdfplumber`)
- OCR для изображений JPG/PNG (`pytesseract` + Tesseract v5.5.0)
- LLM через Ollama локально (`qwen2.5:3b`)
- Валидация реквизитов (ИНН, КПП, ОГРН, БИК, счета)
- Экспорт в JSON + XLSX + DOCX
- CLI интерфейс (`scripts/run_cli.py`)

### 🔲 В планах
- [ ] OCR для сканированных PDF (pdf_scan ветка)
- [ ] Flask веб-интерфейс
- [ ] Batch обработка через веб
- [ ] Улучшение промпта (company_name, ceo_position)

---

## Структура проекта

```
requisites_extractor/
├── app/
│   ├── core/
│   │   ├── constants.py        # IMAGE_EXTENSIONS, MAX_FILE_SIZE и т.д.
│   │   ├── enums.py            # DocumentType, ExtractorType, LLMProvider, ExportFormat
│   │   └── exceptions.py       # UnsupportedFileTypeError, TextExtractionError и т.д.
│   ├── schemas/
│   │   ├── document.py         # DocumentInput
│   │   ├── extraction.py       # TextExtractionResult, NormalizedText, LLMExtractionResult
│   │   ├── requisites.py       # RequisitesData (16 полей)
│   │   └── validation.py       # ValidationReport, FieldValidation, PipelineResult
│   ├── extractors/
│   │   ├── docx_extractor.py
│   │   ├── pdf_extractor.py
│   │   └── image_ocr_extractor.py   # pytesseract, возвращает TextExtractionResult
│   ├── services/
│   │   ├── pipeline_service.py      # run_pipeline() — главная точка входа
│   │   ├── routing_service.py       # detect_document_type()
│   │   ├── text_extraction_service.py
│   │   ├── normalization_service.py
│   │   ├── validation_service.py    # validate_requisites()
│   │   └── export_service.py
│   ├── llm/
│   │   ├── mock_client.py
│   │   ├── ollama_client.py
│   │   └── openai_client.py
│   ├── exporters/
│   │   ├── json_exporter.py
│   │   ├── xlsx_exporter.py
│   │   ├── docx_exporter.py
│   │   └── zip_exporter.py
│   ├── validators/
│   │   ├── inn_validator.py
│   │   ├── kpp_validator.py
│   │   ├── ogrn_validator.py
│   │   ├── bik_validator.py
│   │   └── account_validator.py
│   ├── web/                         # 🔲 Flask — ещё не реализован
│   └── config.py
├── scripts/
│   └── run_cli.py
├── uploads/
├── exports/
├── processed/
├── logs/
├── shablon.docx
├── .env                             # настройки (не коммитить!)
├── fix_structure.py
└── requirements.txt
```

---

## Установка и запуск

### Требования
- Python 3.11+
- Ollama (https://ollama.com/download/windows)
- Tesseract OCR v5.5.0 (https://github.com/UB-Mannheim/tesseract/wiki)
- GTX 1650 Ti 4GB (или CPU)

### 1. Виртуальное окружение

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

### 2. Файл `.env`

```ini
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
PROMPT_VERSION=v1
LLM_TIMEOUT_SECONDS=120.0
OPENAI_API_KEY=none
TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
```

### 3. Tesseract в PATH

```powershell
$env:PATH += ";C:\\Program Files\\Tesseract-OCR"
[Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\\Program Files\\Tesseract-OCR", "User")
```

### 4. Ollama — модель уже скачана

```powershell
ollama list
# NAME              ID    SIZE    MODIFIED
# qwen2.5:3b        ...   2.0GB   ...
```

> На Windows Ollama стартует автоматически как фоновый сервис.

---

## CLI команды

```powershell
# Обработать один файл
python scripts/run_cli.py process путь/к/файлу.pdf --show-result

# Batch обработка папки
python scripts/run_cli.py batch C:\\путь\\к\\папке -e pdf docx

# Текущие настройки
python scripts/run_cli.py info

# Файл с пробелами в имени — обязательно в кавычках
python scripts/run_cli.py process "C:\\Users\\Admin\\Desktop\\Карта СИТИТЕК (Точка).docx" --show-result
```

### Поддерживаемые форматы

| Формат | Метод |
|--------|-------|
| `.docx` | python-docx |
| `.pdf` (цифровой) | pdfplumber |
| `.pdf` (скан) | 🔲 в разработке |
| `.jpg`, `.jpeg`, `.png`, `.tiff` | pytesseract |

---

## Поля реквизитов (16 штук)

| Поле | Описание | Валидация |
|------|----------|-----------|
| `company_name` | Полное наименование | — |
| `short_name` | Краткое наименование | — |
| `legal_address` | Юридический адрес | — |
| `postal_address` | Почтовый адрес | — |
| `ogrn` | ОГРН | 13 или 15 цифр |
| `inn` | ИНН | 10 или 12 цифр + контрольная сумма |
| `kpp` | КПП | 9 цифр |
| `bank_name` | Наименование банка | — |
| `checking_account` | Расчётный счёт | 20 цифр |
| `correspondent_account` | Корреспондентский счёт | 20 цифр |
| `bik` | БИК | 9 цифр, начинается с 04 |
| `ceo_position` | Должность руководителя | — |
| `ceo_fio_full` | ФИО руководителя | — |
| `ceo_fio` | ФИО сокращённо | — |
| `phone` | Телефон | — |
| `email` | Email | — |

---

## Результаты тестирования

| Файл | Тип | Заполнено | Статус | Время LLM |
|------|-----|-----------|--------|-----------|
| `karta_rassvet.pdf` | PDF цифровой | 15/16 (94%) | ⚠️ needs_review | ~14 сек |
| `Карта СИТИТЕК (Точка).docx` | DOCX | 14/16 (88%) | ✅ done | ~22 сек |
| `test_real.docx` | DOCX тест | 15/16 (94%) | ⚠️ needs_review | ~22 сек |

`needs_review` = хотя бы одно поле не прошло валидацию формата.

---

## Известные проблемы

| Проблема | Причина | Решение |
|----------|---------|---------|
| `company_name` часто пустой | Нет явной метки "Полное наименование" | Доработать промпт |
| `ceo_position` пустой | Должность не рядом с ФИО | Доработать промпт |
| БИК с лишним нулём | Ошибка в исходном документе | Норма, валидатор поймает |
| `ollama / gpt-4o-mini` в логах | `llm_model` перекрывает `ollama_model` | Косметика, на работу не влияет |

---

## Следующий шаг — Flask веб-интерфейс

Планируемый функционал:
- Загрузка файла через браузер (drag & drop)
- Отображение извлечённых реквизитов в таблице
- Редактирование полей вручную
- Скачивание JSON / XLSX / DOCX
- История обработанных документов

```powershell
# После реализации:
python scripts/run_web.py
# Открыть: http://localhost:5000
```

---

## LLM провайдеры

| Провайдер | Настройка в .env | Стоимость |
|-----------|-----------------|-----------|
| Ollama (локально) | `LLM_PROVIDER=ollama` | Бесплатно |
| OpenAI через прокси | `LLM_PROVIDER=openai` + `OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1` | ~$0.0002/документ |
| Mock (тест) | `LLM_PROVIDER=mock` | Бесплатно, всегда null |

> Для OpenAI из РФ используй прокси: proxyapi.ru или vsegpt.ru
'''

with open(os.path.expanduser('~/output/README.md'), 'w', encoding='utf-8') as f:
    f.write(readme)
print("OK", len(readme), "chars")

import json, os
os.makedirs(os.path.expanduser('~/output'), exist_ok=True)

# Share README
with open(os.path.expanduser('~/output/README.md'), 'r') as f:
    content = f.read()
print(f"README ready: {len(content)} chars")