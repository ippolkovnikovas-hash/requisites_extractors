"""
Тесты повторного распознавания числовых строк через char_whitelist.

Модуль `app.ocr.numeric_rerun` — чистый, без Tesseract: эвристики тестируются
напрямую, оркестрация — с подменённым бэкендом. Сама идея из разбора пайплайна
(Э13/Э18): OCR путает цифры с буквами («О»↔«0», «З»↔«3»), а повторный вызов
Tesseract на обрезанном регионе с `tessedit_char_whitelist` заставляет его
выдавать только цифры.
"""

from app.ocr.numeric_rerun import (
    digit_density,
    is_numeric_candidate,
    rerun_numeric_lines,
)

# ── digit_density ────────────────────────────────────────────────────────────


def test_digit_density_empty_is_zero():
    assert digit_density("") == 0.0


def test_digit_density_pure_digits_is_one():
    assert digit_density("7744012347") == 1.0


def test_digit_density_mixed_with_letters():
    # «О» и «Z» — типичные OCR-подмены цифр; они не цифры и снижают плотность.
    assert digit_density("77O4O1Z347") == 0.7


def test_digit_density_ignores_whitespace():
    # Пробелы не входят ни в числитель, ни в знаменатель.
    assert digit_density(" 12 34 ") == 1.0


# ── is_numeric_candidate ─────────────────────────────────────────────────────


def test_candidate_pure_number():
    assert is_numeric_candidate("7744012347") is True


def test_candidate_letter_confusion_is_candidate():
    # Число с единичными буквами-подменами — ровно тот случай, ради которого
    # нужен повторный прогон с whitelist.
    assert is_numeric_candidate("77O4O1Z347") is True


def test_candidate_short_sequence_rejected():
    # Слишком короткое — не похоже на реквизит.
    assert is_numeric_candidate("12345") is False


def test_candidate_low_digit_density_rejected():
    assert is_numeric_candidate("АО Ромашка") is False


def test_candidate_with_glued_label_skipped():
    # guard по меткам: «ИНН7744012347» — метка прилипла к числу, whitelist её
    # уничтожил бы. Не трогаем.
    assert is_numeric_candidate("ИНН7744012347") is False


def test_candidate_label_and_value_skipped():
    # «ИНН 7744012347» отсекается и по метке, и по внутреннему пробелу.
    assert is_numeric_candidate("ИНН 7744012347") is False


def test_candidate_classifier_code_glued_label_skipped():
    # Регрессия реального замера (05.09.2026): «ОКТМО:07727000» проходила как
    # числовой кандидат — LABEL_WORDS не знал про коды классификаторов, только
    # про ИНН/КПП/БИК/ОГРН/счета. Whitelist-прогон стирал метку «ОКТМО:»
    # целиком, что меняло контекст документа и уводило ответ LLM по никак не
    # связанным полям (bank_name, ceo_fio, company_name) на конкретном
    # документе. Коды классификаторов — тот же класс меток, что и у ОГРН,
    # который проект уже отдельно бережёт от путаницы (ogrn_validator).
    assert is_numeric_candidate("ОКТМО:07727000") is False
    assert is_numeric_candidate("ОКПО:28451997") is False
    assert is_numeric_candidate("ОКАТО:07427000000") is False
    assert is_numeric_candidate("ОКОГУ:4210014") is False
    assert is_numeric_candidate("ОКФС:16") is False
    assert is_numeric_candidate("ОКОПФ:12300") is False
    assert is_numeric_candidate("ОКВЭД:42.11") is False


def test_candidate_multiple_tokens_rejected():
    # Два числа через пробел не перераспознаём: digits-only whitelist склеил бы
    # их в один длинный, а regex-слой и так умеет нормализовать пробелы.
    assert is_numeric_candidate("7744012347 774401001") is False


def test_candidate_whitespace_only_rejected():
    assert is_numeric_candidate("   ") is False


# ── rerun_numeric_lines ──────────────────────────────────────────────────────


class FakeBackend:
    """Бэкенд с предзаданными строками/bbox и ответами recognize_region."""

    def __init__(self, lines_and_boxes, recognized):
        self._lines_and_boxes = lines_and_boxes
        self._recognized = list(recognized)
        self.calls = []

    def image_to_lines_with_boxes(self, image, lang="rus+eng"):
        return self._lines_and_boxes

    def recognize_region(self, image, bbox, whitelist, lang="rus+eng"):
        self.calls.append((bbox, whitelist))
        return self._recognized.pop(0)


def test_rerun_replaces_numeric_candidate():
    backend = FakeBackend(
        [("7744012347", (10, 20, 100, 40))],
        ["7744012348"],
    )
    assert rerun_numeric_lines(backend, None) == ["7744012348"]
    assert backend.calls == [((10, 20, 100, 40), "0123456789")]


def test_rerun_leaves_label_line_untouched():
    backend = FakeBackend([("ИНН 7744012347", (10, 20, 100, 40))], [])
    assert rerun_numeric_lines(backend, None) == ["ИНН 7744012347"]
    assert backend.calls == []


def test_rerun_skips_line_without_bbox():
    # Бэкенд без геометрии (easyocr, базовая реализация) — перераспознавать
    # нечем, строку возвращаем как есть.
    backend = FakeBackend([("7744012347", None)], [])
    assert rerun_numeric_lines(backend, None) == ["7744012347"]
    assert backend.calls == []


def test_rerun_falls_back_to_original_on_empty():
    # Пустой результат повторного прогона — оставляем исходную строку, а не
    # теряем значение.
    backend = FakeBackend([("7744012347", (0, 0, 50, 20))], [""])
    assert rerun_numeric_lines(backend, None) == ["7744012347"]
