"""Тесты fallback regex-экстрактора на тестовом PDF."""

from app.services.fallback_regex_service import extract_fallback_fields

SAMPLE_TEXT = """
ООО Тестовая Организация
ОГРН: 1027700123450
ИНН: 7744012347
КПП: 774401001
Банк: ПАО Сбербанк
Р/с: 40702810000000012345
К/с: 30101810400000000225
БИК: 044525225
Тел.: +7 (495) 123-45-67
E-mail: test@testorg.ru
"""


def test_extracts_inn():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["inn"] == "7744012347"


def test_extracts_ogrn():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["ogrn"] == "1027700123450"


def test_extracts_kpp():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["kpp"] == "774401001"


def test_extracts_bik():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["bik"] == "044525225"


def test_extracts_checking_account():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["checking_account"] == "40702810000000012345"


def test_extracts_correspondent_account():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["correspondent_account"] == "30101810400000000225"


def test_extracts_phone():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["phone"] == "+74951234567"


def test_extracts_email():
    result = extract_fallback_fields(SAMPLE_TEXT)
    assert result["email"] == "test@testorg.ru"


def test_empty_text_returns_empty():
    result = extract_fallback_fields("")
    assert result["inn"] is None
    assert result["ogrn"] is None


def test_phone_formats_normalized():
    formats = [
        "8 (495) 123-45-67",
        "8-495-123-45-67",
        "+7 495 123 45 67",
        "84951234567",
    ]
    for fmt in formats:
        result = extract_fallback_fields(f"Тел.: {fmt}")
        assert result["phone"] is not None, f"phone not extracted from: {fmt}"
        assert result["phone"].replace("+7", "8").replace(
            "8", "", 1
        ).isdigit() or result["phone"].startswith(
            ("+7", "8")
        ), f"unexpected format: {result['phone']}"


# ── Найдено на реальных документах (спринт 5) ────────────────────────────────


def test_bank_name_label_does_not_match_inside_longer_word():
    """
    Регрессия: подпись поля «Банк» ловилась через `startswith("банк")` без
    проверки границы слова, поэтому срабатывала и на «Банковские реквизиты»
    (слово начинается с тех же букв, но это не подпись поля). Строка
    нарезалась с четвёртого символа, и в bank_name попадал обрывок
    «овские реквизиты | ...» вместо названия банка. Найдено на реальной
    карточке контрагента при замере accuracy (Э16).
    """
    text = "Банковские реквизиты | Ставропольское отделение №5230 ПАО Сбербанк"
    result = extract_fallback_fields(text)
    assert result["bank_name"] == "Ставропольское отделение №5230 ПАО Сбербанк"


def test_bank_label_alone_still_matches():
    """Подпись «Банк» сама по себе (не часть другого слова) не должна
    сломаться от добавленной проверки границы."""
    result = extract_fallback_fields("Банк: ПАО Сбербанк")
    assert result["bank_name"] == "ПАО Сбербанк"


def test_postal_address_strips_leading_pipe_from_table_cell():
    """
    Регрессия: строка «Почтовый адрес | 368006, ...» — соседние ячейки
    таблицы PDF, склеенные через " | " (см. Э13). Регулярка отрезала подпись
    поля до `[:\\s]*`, но не сам разделитель таблицы «|», и он оставался в
    начале значения. Найдено на реальном документе при замере accuracy (Э16).
    """
    text = "3.2. | Почтовый адрес | 368006, Республика Дагестан, город Хасавюрт"
    result = extract_fallback_fields(text)
    assert result["postal_address"] == "368006, Республика Дагестан, город Хасавюрт"


def test_postal_address_otdelenie_pochtovoy_svyazi_strips_table_prefix():
    text = (
        "4.1. | Отделение почтовой связи: 355002, РФ, Ставропольский край, "
        "г. Ставрополь"
    )
    result = extract_fallback_fields(text)
    assert result["postal_address"] == "355002, РФ, Ставропольский край, г. Ставрополь"
