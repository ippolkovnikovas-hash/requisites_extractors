"""
Повторное распознавание числовых строк через `char_whitelist`.

Первопричина из разбора пайплайна (Э13/Э18): Tesseract путает цифры с
похожими по начертанию буквами («О»↔«0», «З»↔«3», «S»↔«5»), причём не только
в однозначных случаях, которые ловит `fold_numeric_confusables`. Повторный
вызов на обрезанном регионе с `tessedit_char_whitelist` заставляет Tesseract
выдавать только цифры — тем самым снимая и неоднозначные подмены.

Модуль намеренно чистый: эвристики не зависят от Tesseract и тестируются
напрямую, а `rerun_numeric_lines` получает бэкенд извне.
"""

# Разрешённые символы повторного прогона. Только цифры — без пробела: кандидат
# по построению не содержит пробелов (см. `is_numeric_candidate`), так что
# включение пробела в whitelist только открыло бы путь к случайному шуму.
NUMERIC_WHITELIST = "0123456789"

# Метки числовых полей (в нижнем регистре). Если метка прилипла к числу
# («ИНН7744012347»), whitelist-прогон уничтожил бы её, а regex-слой потерял бы
# опору. Поэтому такие строки не перераспознаём — это и есть «guard по меткам».
#
# Коды классификаторов (ОКПО/ОКАТО/ОКТМО/...) — тот же класс меток: короткие,
# без внутренних пробелов, с высокой долей цифр после двоеточия. Без этого
# guard'а такая строка проходила как «числовой кандидат», и whitelist-прогон
# стирал метку целиком (найдено реальным замером 05.09.2026 на «ОКТМО:...» —
# менял контекст документа и уводил ответ LLM по несвязанным полям). Тот же
# класс путаницы уже отдельно учтён в `ogrn_validator`.
LABEL_WORDS = (
    "инн",
    "кпп",
    "бик",
    "огрн",
    "р/с",
    "к/с",
    "рс",
    "кс",
    "расч",
    "корр",
    "окпо",
    "окато",
    "октмо",
    "окогу",
    "окфс",
    "окопф",
    "оквэд",
)

_MIN_LENGTH = 6
_MIN_DIGIT_DENSITY = 0.5


def digit_density(text: str) -> float:
    """Доля цифр среди непустых символов строки, от 0.0 до 1.0."""
    significant = [c for c in text if not c.isspace()]
    if not significant:
        return 0.0
    return sum(c.isdigit() for c in significant) / len(significant)


def is_numeric_candidate(text: str) -> bool:
    """
    Похожа ли строка на числовой реквизит, который стоит перераспознать.

    Условия: не короче `_MIN_LENGTH`, без метки поля, без внутренних пробелов
    (один токен) и с высокой долей цифр. Последнее условие важно: два числа
    через пробел мы не трогаем, чтобы digits-only whitelist не склеил их в
    один длинный — пробелы внутри чисел и так снимает нормализация.
    """
    stripped = text.strip()
    if not stripped or len(stripped) < _MIN_LENGTH:
        return False
    lowered = stripped.lower()
    if any(label in lowered for label in LABEL_WORDS):
        return False
    if any(c.isspace() for c in stripped):
        return False
    return digit_density(stripped) >= _MIN_DIGIT_DENSITY


def rerun_numeric_lines(backend, image, lang: str = "rus+eng") -> list[str]:
    """
    Строки OCR с повторным распознаванием числовых кандидатов.

    Берёт строки с bbox через `image_to_lines_with_boxes`, для числовых
    кандидатов с доступной геометрией повторно распознаёт обрезанный регион с
    `NUMERIC_WHITELIST`. Бэкенды без bbox (easyocr, базовая реализация)
    возвращают строки как есть — перераспознавать им нечем.
    """
    result: list[str] = []
    for text, bbox in backend.image_to_lines_with_boxes(image, lang=lang):
        if bbox is None or not is_numeric_candidate(text):
            result.append(text)
            continue
        recognized = backend.recognize_region(image, bbox, NUMERIC_WHITELIST, lang=lang)
        result.append(recognized or text)
    return result
