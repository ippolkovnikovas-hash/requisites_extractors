"""
Unit-тесты валидатора email.

Контракт: raw_value (не меняется), normalized_value (домен -> нижний регистр,
local-part без изменений; несколько адресов через ", "), valid, is_missing,
warning (у этого валидатора всегда None — только жёсткая структурная
проверка), reason.

None/""/пробелы -> is_missing=True, valid=True.

Несколько адресов разделяются по "," ";" или переносу строки, каждый
проверяется независимо; если хотя бы один кандидат не проходит формат —
valid=False для всего поля.

Разрешённые символы: local-part — A-Za-z0-9._%+-; домен — A-Za-z0-9.-, домен
обязан содержать точку. Кириллица нигде не поддерживается (не IDN/punycode —
жёсткая ошибка как обычный недопустимый символ). Проверка исключительно
синтаксическая: без DNS/MX/SMTP/сети.
"""
import pytest

from app.validators.email_validator import validate_email

# ── Валидные адреса ───────────────────────────────────────────────────────────

def test_email_valid_simple():
    result = validate_email("user@example.ru")
    assert result.valid, f"expected valid email, got: {result.reason}"
    assert not result.is_missing
    assert result.warning is None
    assert result.normalized_value == "user@example.ru"


def test_email_valid_plus_addressing():
    result = validate_email("user+tag@example.ru")
    assert result.valid
    assert result.warning is None


def test_email_valid_mixed_case_domain():
    result = validate_email("user@EXAMPLE.RU")
    assert result.valid
    assert result.normalized_value == "user@example.ru"


def test_email_valid_mixed_case_local_part_preserved():
    result = validate_email("User.Name@example.ru")
    assert result.valid
    assert result.normalized_value == "User.Name@example.ru"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_email_missing_variants(value):
    result = validate_email(value)
    assert result.valid
    assert result.is_missing
    assert result.warning is None
    assert result.raw_value == value


# ── Несколько адресов ─────────────────────────────────────────────────────────

def test_email_multiple_valid_comma_separated():
    result = validate_email("a@example.ru, b@example.com")
    assert result.valid
    assert result.normalized_value == "a@example.ru, b@example.com"


def test_email_multiple_valid_semicolon_separated():
    result = validate_email("a@example.ru; b@example.com")
    assert result.valid
    assert result.normalized_value == "a@example.ru, b@example.com"
    assert result.raw_value == "a@example.ru; b@example.com"


def test_email_multiple_valid_newline_separated():
    result = validate_email("a@example.ru\nb@example.com")
    assert result.valid
    assert result.normalized_value == "a@example.ru, b@example.com"


def test_email_one_bad_candidate_among_valid_fails_whole_field():
    result = validate_email("a@example.ru, not-an-email")
    assert not result.valid


def test_email_never_produces_warning():
    """Валидатор бинарный: у него нет warning-ветки вообще."""
    for value in ("user@example.ru", "a@example.ru, b@example.com", None):
        assert validate_email(value).warning is None


# ── Базовая структура: @, local-part, домен ──────────────────────────────────

def test_email_no_at_symbol_is_hard_error():
    result = validate_email("userexample.ru")
    assert not result.valid
    assert "@" in result.reason


def test_email_multiple_at_symbols_is_hard_error():
    result = validate_email("user@@example.ru")
    assert not result.valid
    assert "@" in result.reason


def test_email_empty_local_part_is_hard_error():
    result = validate_email("@example.ru")
    assert not result.valid
    assert "до @" in result.reason


def test_email_empty_domain_is_hard_error():
    result = validate_email("user@")
    assert not result.valid
    assert "пустой домен" in result.reason


def test_email_domain_without_dot_is_hard_error():
    result = validate_email("user@example")
    assert not result.valid
    assert "точку" in result.reason


def test_email_internal_space_is_hard_error():
    result = validate_email("user @example.ru")
    assert not result.valid
    assert "недопустимые символы" in result.reason


def test_email_disallowed_character_is_hard_error():
    result = validate_email("user!@example.ru")
    assert not result.valid
    assert "недопустимые символы" in result.reason


# ── Кириллица — явно hard error, не отдельный IDN-сценарий ──────────────────

def test_email_cyrillic_local_part_is_hard_error():
    """IDN/punycode не поддерживается — кириллица трактуется как недопустимый символ."""
    result = validate_email("пользователь@example.ru")
    assert not result.valid
    assert "недопустимые символы" in result.reason


def test_email_cyrillic_domain_is_hard_error():
    result = validate_email("user@пример.рф")
    assert not result.valid
    assert "недопустимые символы" in result.reason


# ── Точки в local-part: начало/конец/подряд ──────────────────────────────────

@pytest.mark.parametrize("value", [
    "user..name@example.ru",  # двойная точка
    ".user@example.ru",       # точка в начале
    "user.@example.ru",       # точка в конце
])
def test_email_local_part_dot_placement_is_hard_error(value):
    result = validate_email(value)
    assert not result.valid, f"expected hard error for {value!r}"
    assert "точка в local-part" in result.reason


# ── Точки в домене: начало/конец/подряд ──────────────────────────────────────

@pytest.mark.parametrize("value", [
    "user@example..ru",   # двойная точка
    "user@.example.ru",   # точка в начале
    "user@example.ru.",   # точка в конце
])
def test_email_domain_dot_placement_is_hard_error(value):
    result = validate_email(value)
    assert not result.valid, f"expected hard error for {value!r}"
    assert "точка в домене" in result.reason


# ── Дефис в начале/конце доменной метки ──────────────────────────────────────

@pytest.mark.parametrize("value", [
    "user@-example.ru",
    "user@example-.ru",
])
def test_email_domain_label_hyphen_placement_is_hard_error(value):
    result = validate_email(value)
    assert not result.valid, f"expected hard error for {value!r}"
    assert "дефис" in result.reason
