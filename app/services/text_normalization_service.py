"""
Нормализация сырого текста перед отправкой в LLM.

Проблемы которые решаем:
  - OCR-шум: случайные символы, разорванные слова
  - Артефакты pdfplumber: двойные пробелы, лишние переносы строк
  - DOCX-артефакты: повторяющиеся заголовки колонтитулов
  - Мусорные Unicode-символы (неразрывные пробелы, BOM, управляющие символы)
  - Слишком длинный текст: обрезаем до MAX_CHARS чтобы не превышать context window LLM
"""

import re
import unicodedata
from loguru import logger

from app.schemas.extraction import NormalizedText

# Лимит символов для LLM (GPT-4o-mini ~128k токенов, но реквизиты — всегда в начале)
MAX_CHARS = 12_000


def normalize_text(raw_text: str) -> NormalizedText:
    original = raw_text
    text = raw_text

    # 1. Unicode normalization — NFKC приводит лигатуры и "странные" символы к базовым
    text = unicodedata.normalize("NFKC", text)

    # 2. Удаляем управляющие символы кроме \n и \t
    text = re.sub(r"[^\S\n\t ]+", " ", text)          # прочие whitespace → пробел
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 3. Неразрывные пробелы и похожие → обычный пробел
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")

    # 4. Схлопываем пробелы внутри строки (но не переносы)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # 5. Убираем пробелы в начале/конце каждой строки
    lines = [line.strip() for line in text.splitlines()]

    # 6. Склеиваем оборванные строки:
    #    если строка не заканчивается на пунктуацию и следующая начинается со строчной —
    #    скорее всего OCR/PDF разбил одно предложение на две строки
    merged: list[str] = []
    for i, line in enumerate(lines):
        if not line:
            merged.append("")
            continue
        if (
            merged
            and merged[-1]
            and not re.search(r"[.!?:;,\-–—|]$", merged[-1])
            and re.match(r"^[а-яёa-z0-9(]", line)
        ):
            merged[-1] = merged[-1] + " " + line
        else:
            merged.append(line)

    # 7. Убираем более 2 пустых строк подряд
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(merged))

    # 8. Финальный trim
    text = text.strip()

    # 9. Обрезаем до лимита LLM с предупреждением
    warnings_in_meta = []
    if len(text) > MAX_CHARS:
        logger.warning(
            "Text truncated before LLM",
            original_chars=len(text),
            max_chars=MAX_CHARS,
        )
        text = text[:MAX_CHARS]
        warnings_in_meta.append(f"Text truncated to {MAX_CHARS} chars")

    logger.debug(
        "Text normalization done",
        before=len(original),
        after=len(text),
        reduction_pct=round((1 - len(text) / max(len(original), 1)) * 100, 1),
    )

    return NormalizedText(
        original_text=original,
        normalized_text=text,
        char_count_before=len(original),
        char_count_after=len(text),
    )