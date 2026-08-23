"""
Тесты нормализации текста перед отправкой в LLM.

Отдельно проверяется OCR-ветка. Функции `split_classifiers_block()`,
`normalize_requisite_numbers()` и `normalize_ocr_text()` были написаны давно, но
не вызывались ниоткуда — здесь фиксируется контракт и факт их подключения к
`normalize_text()`.
"""

import pytest

from app.core.constants import NORMALIZE_MAX_CHARS
from app.services.text_normalization_service import (
    normalize_ocr_text,
    normalize_requisite_numbers,
    normalize_text,
    split_classifiers_block,
)

# ── Базовая очистка ──────────────────────────────────────────────────────────


def test_normalize_collapses_repeated_spaces():
    result = normalize_text("ООО    Ромашка")
    assert result.normalized_text == "ООО Ромашка"


def test_normalize_strips_non_breaking_spaces():
    result = normalize_text("ИНН 7744012347")
    assert " " not in result.normalized_text
    assert result.normalized_text == "ИНН 7744012347"


def test_normalize_removes_bom_and_zero_width():
    result = normalize_text("﻿ИНН​ 7744012347")
    assert "﻿" not in result.normalized_text
    assert "​" not in result.normalized_text


def test_normalize_removes_control_characters():
    result = normalize_text("ИНН\x07 7744012347")
    assert "\x07" not in result.normalized_text


def test_normalize_trims_each_line():
    result = normalize_text("  ООО Ромашка  \n   ИНН 7744012347   ")
    assert result.normalized_text == "ООО Ромашка\nИНН 7744012347"


def test_normalize_collapses_more_than_two_blank_lines():
    result = normalize_text("ООО Ромашка\n\n\n\n\nИНН 7744012347")
    assert "\n\n\n" not in result.normalized_text


def test_normalize_reports_char_counts():
    raw = "ООО    Ромашка"
    result = normalize_text(raw)
    assert result.original_text == raw
    assert result.char_count_before == len(raw)
    assert result.char_count_after == len(result.normalized_text)


def test_normalize_empty_text_does_not_crash():
    result = normalize_text("")
    assert result.normalized_text == ""
    assert result.char_count_before == 0


# ── Склейка оборванных строк ─────────────────────────────────────────────────


def test_normalize_merges_line_broken_mid_sentence():
    """Строка не кончается пунктуацией, следующая начинается со строчной."""
    result = normalize_text("Общество с ограниченной\nответственностью Ромашка")
    assert result.normalized_text == "Общество с ограниченной ответственностью Ромашка"


def test_normalize_does_not_merge_after_punctuation():
    result = normalize_text("ООО Ромашка,\nИНН 7744012347")
    assert "\n" in result.normalized_text


def test_normalize_does_not_merge_before_capital_letter():
    result = normalize_text("ООО Ромашка\nИНН 7744012347")
    assert "\n" in result.normalized_text


# ── Обрезка по лимиту ────────────────────────────────────────────────────────


def test_normalize_truncates_to_limit():
    result = normalize_text("а" * (NORMALIZE_MAX_CHARS + 500))
    assert result.char_count_after == NORMALIZE_MAX_CHARS
    assert result.char_count_before == NORMALIZE_MAX_CHARS + 500


def test_normalize_does_not_truncate_below_limit():
    raw = "а" * (NORMALIZE_MAX_CHARS - 1)
    result = normalize_text(raw)
    assert result.char_count_after == NORMALIZE_MAX_CHARS - 1


# ── normalize_requisite_numbers ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "line,expected",
    [
        ("ИНН 7744 012347", "ИНН 7744012347"),
        ("КПП 7744 01001", "КПП 774401001"),
        ("ОГРН 1027 700 123450", "ОГРН 1027700123450"),
        ("БИК 044 525 225", "БИК 044525225"),
        ("Р/с 4070 2810 2000 0001 2345", "Р/с 40702810200000012345"),
        ("К/с 3010 1810 4000 0000 0225", "К/с 30101810400000000225"),
    ],
)
def test_requisite_numbers_glued_on_labeled_lines(line, expected):
    assert normalize_requisite_numbers(line) == expected


def test_requisite_numbers_untouched_without_label():
    """В строке без метки реквизита цифры склеивать нельзя — там может быть дата."""
    line = "Договор от 12 05 2026 года"
    assert normalize_requisite_numbers(line) == line


def test_requisite_numbers_processes_only_matching_lines():
    text = "Дата 12 05 2026\nИНН 7744 012347"
    result = normalize_requisite_numbers(text)
    assert "12 05 2026" in result
    assert "7744012347" in result


def test_requisite_numbers_label_matching_is_case_insensitive():
    assert normalize_requisite_numbers("инн 7744 012347") == "инн 7744012347"


# ── split_classifiers_block ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "classifier", ["ОКПО", "ОКТМО", "ОКВЭД", "ОКАТО", "ОКОПФ", "ОКФС", "КБК"]
)
def test_classifier_moved_to_new_line(classifier):
    result = split_classifiers_block(f"ИНН 7744012347 {classifier} 12345678")
    assert f"\n{classifier}" in result


def test_classifier_already_on_new_line_is_left_alone():
    text = "ИНН 7744012347\nОКПО 12345678"
    assert split_classifiers_block(text) == text


def test_classifier_split_helps_separate_ogrn_from_okpo():
    """Ради этого всё и затевалось: ОКПО не должен слипаться с ОГРН в одну строку."""
    result = split_classifiers_block("ОГРН 1027700123450 ОКПО 12345678")
    lines = [ln for ln in result.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "1027700123450" in lines[0]
    assert "12345678" in lines[1]


# ── normalize_ocr_text: обе операции вместе ──────────────────────────────────


def test_normalize_ocr_text_applies_both_steps():
    result = normalize_ocr_text("ИНН 7744 012347 ОКПО 1234 5678")
    assert "7744012347" in result
    assert "\nОКПО" in result


# ── Подключение OCR-ветки к normalize_text ───────────────────────────────────


def test_normalize_text_applies_ocr_cleanup_when_asked():
    result = normalize_text("ИНН 7744 012347 ОКПО 12345678", ocr=True)
    assert "7744012347" in result.normalized_text
    assert "ОКПО" in result.normalized_text


def test_normalize_text_does_not_glue_digits_without_ocr_flag():
    """Для документов с текстовым слоем пробелы в числах осмысленны."""
    result = normalize_text("ИНН 7744 012347")
    assert "7744 012347" in result.normalized_text


def test_normalize_text_ocr_flag_defaults_to_false():
    plain = normalize_text("ИНН 7744 012347")
    explicit = normalize_text("ИНН 7744 012347", ocr=False)
    assert plain.normalized_text == explicit.normalized_text


def test_normalize_text_ocr_keeps_original_text_untouched():
    raw = "ИНН 7744 012347 ОКПО 12345678"
    result = normalize_text(raw, ocr=True)
    assert result.original_text == raw
