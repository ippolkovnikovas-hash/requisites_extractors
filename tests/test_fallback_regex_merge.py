"""
Тесты слияния результатов LLM и regex-слоя.

`merge_llm_and_fallback()` решает, чьё значение попадёт в итог, и помечает
источник каждого поля. Логика правил разная для каждого реквизита: где-то
побеждает более длинная строка, где-то — правильная длина числа или префикс.

Здесь же покрывается разбор ФИО руководителя, который regex-слой делает
самостоятельно: определение отчества по суффиксу, перестановка порядка слов и
построение краткой формы.
"""

import pytest

from app.services.fallback_regex_service import (
    extract_fallback_fields,
    merge_llm_and_fallback,
)

# ── Базовое поведение слияния ────────────────────────────────────────────────


def test_llm_value_wins_when_regex_empty():
    merged, source = merge_llm_and_fallback({"inn": "7744012347"}, {"inn": None})
    assert merged["inn"] == "7744012347"
    assert source["inn"] == "llm"


def test_regex_fills_field_missing_in_llm():
    merged, source = merge_llm_and_fallback({"inn": None}, {"inn": "7744012347"})
    assert merged["inn"] == "7744012347"
    assert source["inn"] == "regex"


def test_regex_fills_field_absent_from_llm_dict_entirely():
    merged, source = merge_llm_and_fallback({}, {"bik": "044525225"})
    assert merged["bik"] == "044525225"
    assert source["bik"] == "regex"


def test_empty_string_counts_as_missing():
    merged, source = merge_llm_and_fallback({"kpp": ""}, {"kpp": "774401001"})
    assert merged["kpp"] == "774401001"
    assert source["kpp"] == "regex"


def test_source_map_marks_untouched_llm_fields():
    merged, source = merge_llm_and_fallback(
        {"inn": "7744012347", "kpp": "774401001"}, {}
    )
    assert source == {"inn": "llm", "kpp": "llm"}


def test_empty_llm_field_without_regex_has_no_source():
    _, source = merge_llm_and_fallback({"inn": None}, {})
    assert "inn" not in source


# ── Числовые реквизиты: побеждает правильная длина ───────────────────────────


@pytest.mark.parametrize(
    "field,llm_value,regex_value",
    [
        ("inn", "123", "7744012347"),
        ("inn", "123", "500100732259"),
        # ИНН, в который затесался номер счёта
        ("inn", "40702810200000012345", "7744012347"),
        ("kpp", "7744", "774401001"),
        ("ogrn", "102770012345", "1027700123450"),
    ],
)
def test_regex_wins_on_correct_length(field, llm_value, regex_value):
    merged, source = merge_llm_and_fallback({field: llm_value}, {field: regex_value})
    assert merged[field] == regex_value
    assert source[field] == "regex"


@pytest.mark.parametrize(
    "field,llm_value,regex_value",
    [
        ("inn", "7744012347", "123"),
        ("kpp", "774401001", "7744"),
        ("ogrn", "1027700123450", "102770012345"),
    ],
)
def test_llm_wins_when_its_length_is_correct(field, llm_value, regex_value):
    merged, source = merge_llm_and_fallback({field: llm_value}, {field: regex_value})
    assert merged[field] == llm_value
    assert source[field] == "llm"


# ── БИК и счета: важны и длина, и префикс ────────────────────────────────────


def test_bik_regex_wins_on_correct_prefix():
    merged, source = merge_llm_and_fallback({"bik": "144525225"}, {"bik": "044525225"})
    assert merged["bik"] == "044525225"
    assert source["bik"] == "regex"


def test_bik_llm_kept_when_already_correct():
    merged, _ = merge_llm_and_fallback({"bik": "044525225"}, {"bik": "144525225"})
    assert merged["bik"] == "044525225"


def test_checking_account_regex_wins_on_correct_prefix():
    merged, source = merge_llm_and_fallback(
        {"checking_account": "30101810400000000225"},
        {"checking_account": "40702810200000012345"},
    )
    assert merged["checking_account"] == "40702810200000012345"
    assert source["checking_account"] == "regex"


def test_correspondent_account_regex_wins_on_correct_prefix():
    merged, source = merge_llm_and_fallback(
        {"correspondent_account": "40702810200000012345"},
        {"correspondent_account": "30101810400000000225"},
    )
    assert merged["correspondent_account"] == "30101810400000000225"
    assert source["correspondent_account"] == "regex"


def test_correspondent_account_llm_kept_when_correct():
    merged, _ = merge_llm_and_fallback(
        {"correspondent_account": "30101810400000000225"},
        {"correspondent_account": "40702810200000012345"},
    )
    assert merged["correspondent_account"] == "30101810400000000225"


# ── Текстовые поля ───────────────────────────────────────────────────────────


def test_company_name_with_opf_beats_bare_name():
    """Признак победы regex — организационно-правовая форма, а не длина."""
    merged, source = merge_llm_and_fallback(
        {"company_name": "Ромашка"},
        {"company_name": "Общество с ограниченной ответственностью Ромашка"},
    )
    assert merged["company_name"].startswith("Общество")
    assert source["company_name"] == "regex"


def test_company_name_glued_with_next_field_loses():
    """
    Регрессия: правило «длиннее — значит лучше» работало обратно задуманному.
    Чем больше регекс перехватил соседних строк, тем увереннее он побеждал
    корректное значение LLM — и склейка уходила в DOCX.
    """
    merged, source = merge_llm_and_fallback(
        {"company_name": "ООО Ромашка"},
        {"company_name": "ООО Ромашка Юридический адрес: г. Москва ИНН 7744012347"},
    )
    assert merged["company_name"] == "ООО Ромашка"
    assert source["company_name"] == "llm"


def test_legal_address_with_glued_requisites_loses():
    merged, source = merge_llm_and_fallback(
        {"legal_address": "119019, г. Москва, ул. Волхонка, д. 15"},
        {"legal_address": "г. Москва, ул. Волхонка ИНН 7744012347 ОГРН 1027700132195"},
    )
    assert "ИНН" not in merged["legal_address"]
    assert source["legal_address"] == "llm"


def test_company_name_shorter_regex_value_loses():
    merged, _ = merge_llm_and_fallback(
        {"company_name": "Общество с ограниченной ответственностью Ромашка"},
        {"company_name": "Ромашка"},
    )
    assert merged["company_name"].startswith("Общество")


def test_short_name_prefers_compact_value_with_opf():
    merged, source = merge_llm_and_fallback(
        {"short_name": "Общество с ограниченной ответственностью Ромашка"},
        {"short_name": "ООО Ромашка"},
    )
    assert merged["short_name"] == "ООО Ромашка"
    assert source["short_name"] == "regex"


def test_short_name_without_opf_does_not_override():
    merged, _ = merge_llm_and_fallback(
        {"short_name": "ООО Ромашка"}, {"short_name": "Ромашка"}
    )
    assert merged["short_name"] == "ООО Ромашка"


def test_legal_address_longer_value_wins():
    merged, source = merge_llm_and_fallback(
        {"legal_address": "г. Москва"},
        {"legal_address": "119019, г. Москва, ул. Волхонка, д. 15"},
    )
    assert "Волхонка" in merged["legal_address"]
    assert source["legal_address"] == "regex"


def test_postal_address_differing_value_wins():
    merged, source = merge_llm_and_fallback(
        {"postal_address": "г. Москва"}, {"postal_address": "г. Тверь"}
    )
    assert merged["postal_address"] == "г. Тверь"
    assert source["postal_address"] == "regex"


def test_postal_address_identical_value_is_not_marked_regex():
    merged, source = merge_llm_and_fallback(
        {"postal_address": "г. Москва"}, {"postal_address": "г. Москва"}
    )
    assert merged["postal_address"] == "г. Москва"
    assert source["postal_address"] == "llm"


# ── Email и телефон ──────────────────────────────────────────────────────────


def test_email_regex_wins_when_llm_value_is_not_an_address():
    merged, source = merge_llm_and_fallback(
        {"email": "почта отсутствует"}, {"email": "info@example.ru"}
    )
    assert merged["email"] == "info@example.ru"
    assert source["email"] == "regex"


def test_email_llm_kept_when_it_already_has_at_sign():
    merged, _ = merge_llm_and_fallback(
        {"email": "a@example.ru"}, {"email": "b@example.ru"}
    )
    assert merged["email"] == "a@example.ru"


def test_phone_regex_wins_with_eleven_digits():
    merged, source = merge_llm_and_fallback({"phone": "123"}, {"phone": "+79161234567"})
    assert merged["phone"] == "+79161234567"
    assert source["phone"] == "regex"


def test_phone_llm_kept_when_it_has_eleven_digits():
    merged, _ = merge_llm_and_fallback(
        {"phone": "+79161234567"}, {"phone": "+74951234567"}
    )
    assert merged["phone"] == "+79161234567"


def test_phone_regex_wins_when_llm_value_has_no_digits():
    merged, source = merge_llm_and_fallback(
        {"phone": "не указан"}, {"phone": "+79161234567"}
    )
    assert merged["phone"] == "+79161234567"
    assert source["phone"] == "regex"


# ── Неизвестное поле правил не имеет ─────────────────────────────────────────


def test_unknown_field_keeps_llm_value():
    merged, source = merge_llm_and_fallback(
        {"bank_name": "Банк А"}, {"bank_name": "Банк Б"}
    )
    assert merged["bank_name"] == "Банк А"
    assert source["bank_name"] == "llm"


# ── Разбор ФИО руководителя regex-слоем ──────────────────────────────────────


def test_ceo_full_name_after_position():
    result = extract_fallback_fields("Генеральный директор Иванов Иван Иванович")
    assert result["ceo_fio_full"] == "Иванов Иван Иванович"
    assert result["ceo_fio"] == "Иванов И.И."


def test_ceo_short_form_built_from_two_word_name():
    result = extract_fallback_fields("Директор | Смит Джон")
    assert result["ceo_fio"] == "Смит Д."


@pytest.mark.parametrize("separator", ["|", "\t"])
def test_ceo_order_normalized_when_patronymic_is_second(separator):
    """
    «Имя Отчество Фамилия» → «Фамилия Имя Отчество».

    Регрессия: разбор карточки контрагента возвращал сырой порядок и
    перекрывал корректно переставленное значение из _extract_ceo().
    """
    result = extract_fallback_fields(f"Директор {separator} Иван Иванович Петров")
    assert result["ceo_fio_full"] == "Петров Иван Иванович"


def test_ceo_short_form_matches_reordered_surname():
    """Краткая форма должна пересобираться после перестановки, а не остаться
    от прежней «фамилии»."""
    result = extract_fallback_fields("Директор | Иван Иванович Петров")
    assert result["ceo_fio"] == "Петров И.И."


def test_ceo_order_kept_when_patronymic_is_last():
    result = extract_fallback_fields("Директор | Петров Иван Иванович")
    assert result["ceo_fio_full"] == "Петров Иван Иванович"


def test_ceo_order_kept_when_no_patronymic_found():
    result = extract_fallback_fields("Директор | Ким Ли Пак")
    assert result["ceo_fio_full"] == "Ким Ли Пак"


# ── Разделитель подписи поля не должен попадать в значение ───────────────────


@pytest.mark.parametrize(
    "line,field,expected",
    [
        (
            "Полное наименование организации | ООО Ромашка",
            "company_name",
            "ООО Ромашка",
        ),
        ("Краткое наименование организации | ООО Ромашка", "short_name", "ООО Ромашка"),
        ("Банк | ПАО Сбербанк", "bank_name", "ПАО Сбербанк"),
        (
            "Юридический адрес | г. Москва, ул. Волхонка",
            "legal_address",
            "г. Москва, ул. Волхонка",
        ),
        (
            "Почтовый адрес\tг. Москва, ул. Волхонка",
            "postal_address",
            "г. Москва, ул. Волхонка",
        ),
    ],
)
def test_pipe_and_tab_separators_are_stripped(line, field, expected):
    """
    Регрессия: `|` и табуляция не входили в набор обрезаемых символов, и
    значение уходило в документ как «| ООО Ромашка».
    """
    assert extract_fallback_fields(line)[field] == expected


# ── Метка поля не должна съедать начало значения ─────────────────────────────


def test_company_label_does_not_eat_the_value():
    """
    Регрессия: `[^\n]{0,30}` после метки задумывался как «пропустить хвост
    подписи», но он жадный и ничем не ограничен — съедал 30 символов самого
    значения. «Общество с ограниченной ответственностью Ромашка» приходило в
    форму как «тственностью Ромашка».
    """
    result = extract_fallback_fields(
        "Полное наименование: Общество с ограниченной ответственностью Ромашка"
    )
    assert result["company_name"] == "Общество с ограниченной ответственностью Ромашка"


def test_short_name_label_does_not_leak_to_the_next_line():
    """Метка съедала свою строку целиком, `\n?` перешагивал перевод, и в
    краткое наименование попадала следующая строка документа."""
    text = (
        "Сокращённое наименование: ООО Ромашка\n"
        "Юридический адрес: 119019, г. Москва, ул. Волхонка, д. 15\n"
    )
    result = extract_fallback_fields(text)

    assert result["short_name"] == "ООО Ромашка"
    assert result["legal_address"] == "119019, г. Москва, ул. Волхонка, д. 15"


def test_label_on_its_own_line_still_matches():
    """Подпись поля отдельной строкой — обычный вид карточки, и он не должен
    сломаться от требования разделителя."""
    result = extract_fallback_fields("Полное наименование\nАкционерное общество Север")
    assert result["company_name"] == "Акционерное общество Север"


def test_label_with_parenthetical_qualifier_still_matches():
    result = extract_fallback_fields(
        "Полное наименование (по уставу): Акционерное общество Север"
    )
    assert result["company_name"] == "Акционерное общество Север"


def test_ceo_signature_form_initials_before_surname():
    """«Директор И.И. Иванов» — инициалы впереди, приводим к «Иванов И.И.»."""
    result = extract_fallback_fields("Генеральный директор Иванов И.И.")
    assert result["ceo_fio"] == "Иванов И.И."


def test_ceo_position_captured():
    result = extract_fallback_fields("Генеральный директор Иванов Иван Иванович")
    assert result["ceo_position"]
    assert "иректор" in result["ceo_position"]


def test_no_ceo_in_text_leaves_fields_empty():
    result = extract_fallback_fields("ИНН 7744012347")
    assert result["ceo_fio_full"] is None
    assert result["ceo_fio"] is None
