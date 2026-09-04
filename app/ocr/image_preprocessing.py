"""
Общая предобработка изображений для OCR: устранение мелкого наклона и
адаптивная бинаризация. Используется обоими OCR-экстракторами.

Обе функции работают только через Pillow, без numpy и без новых
зависимостей — проект намеренно бережно относится к весу зависимостей (см.
`requirements/easyocr.txt`), а обе задачи решаются достаточно быстро и без
неё на уменьшенной копии изображения.

Мелкий наклон (обычно ±1–5° у фото документа, снятого с рук) — не то же
самое, что ориентация страницы (0/90/180/270), которую находит
`pytesseract.image_to_osd()`. Проверено эмпирически: на синтетическом скане,
наклонённом на 0.4°, OSD стабильно возвращает `Rotate: 0` — угол настолько
мал, что механизм ориентации его просто не видит. Поэтому наклон оценивается
отдельно, методом проекционного профиля.
"""

from PIL import Image

# Диапазон поиска угла: сначала грубо в пределах ±5° с шагом 1°, затем точнее
# вокруг найденного грубого угла с шагом 0.1°. Двухпроходный перебор дешевле
# одного прохода с мелким шагом по всему диапазону.
_COARSE_RANGE = 5.0
_COARSE_STEP = 1.0
_FINE_RANGE = 1.0
_FINE_STEP = 0.1

# Ширина уменьшенной копии для перебора углов. На итоговое качество OCR не
# влияет — угол применяется к изображению в его исходном разрешении.
_SEARCH_WIDTH = 500


def _row_profile_variance(image: Image.Image, angle: float) -> float:
    """
    Дисперсия яркости построчного профиля после поворота на `angle`.

    Ровно выровненный текст даёт резкие перепады между строками текста и
    межстрочными пробелами — высокую дисперсию построчных средних. Наклон
    размывает профиль (соседние строки текста и фона перемешиваются по
    горизонтали) — дисперсия падает. Максимум дисперсии по перебору углов и
    есть угол коррекции.

    Строки схлопываются в один столбец через усредняющий resize — это
    выполняется в C-коде Pillow и не требует numpy или ручных циклов по
    пикселям.
    """
    rotated = image.rotate(angle, resample=Image.Resampling.BILINEAR, fillcolor=255)
    height = rotated.size[1]
    column = rotated.resize((1, height), Image.Resampling.BOX)
    values = list(column.getdata())
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def detect_skew_angle(image: Image.Image) -> float:
    """
    Оценивает угол мелкого наклона методом проекционного профиля.

    Возвращает угол коррекции: `image.rotate(angle)` должен выпрямить
    изображение. На однородном изображении (нет ни одного тёмного пикселя —
    профиль не меняется ни при каком повороте) возвращает `0.0`: без этой
    защиты перебор вернул бы первый проверенный угол просто по порядку, то
    есть случайный поворот пустого кадра.
    """
    gray = image.convert("L")
    width, height = gray.size
    if width == 0 or height == 0:
        return 0.0

    scale = _SEARCH_WIDTH / width
    small = gray.resize(
        (_SEARCH_WIDTH, max(1, round(height * scale))), Image.Resampling.LANCZOS
    )

    best_angle, best_score = 0.0, 0.0

    angle = -_COARSE_RANGE
    while angle <= _COARSE_RANGE + 1e-9:
        score = _row_profile_variance(small, angle)
        if score > best_score:
            best_score, best_angle = score, angle
        angle += _COARSE_STEP

    coarse_angle = best_angle
    angle = coarse_angle - _FINE_RANGE
    while angle <= coarse_angle + _FINE_RANGE + 1e-9:
        score = _row_profile_variance(small, angle)
        if score > best_score:
            best_score, best_angle = score, angle
        angle += _FINE_STEP

    return round(best_angle, 1)


def deskew(image: Image.Image) -> Image.Image:
    """
    Поворачивает изображение на оценённый угол коррекции.

    Если угол найден нулевым — возвращает тот же объект без поворота: любой
    поворот (даже на 0°) проходит через ресемплинг и немного смазывает
    изображение, а на уже выровненном скане в этом смысла нет.
    """
    angle = detect_skew_angle(image)
    if angle == 0.0:
        return image
    return image.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=255)


def otsu_threshold(image: Image.Image) -> int:
    """
    Порог бинаризации по методу Оцу — подбирается по гистограмме самого
    изображения, а не фиксируется заранее.

    Фиксированный порог работает только на изображениях с похожей яркостью
    фона; на фото с неравномерным освещением он либо заливает часть кадра
    чёрным, либо не убирает шум вовсе (проверено эмпирически: на фото с
    неравномерным светом фиксированный порог 170 превратил верно
    распознанное «Р/с» в «РК» — метка потерялась в чёрной заливке). Метод
    Оцу перебирает все 256 возможных порогов и ищет тот, что даёт
    наибольшее разделение между «тёмным» и «светлым» кластерами
    (межклассовую дисперсию) — за один проход по гистограмме, без numpy.
    """
    histogram = image.convert("L").histogram()
    total = sum(histogram)
    if total == 0:
        return 128

    sum_all = sum(i * h for i, h in enumerate(histogram))

    sum_bg = 0.0
    weight_bg = 0
    best_variance = -1.0
    best_threshold = 128

    for t in range(256):
        weight_bg += histogram[t]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break

        sum_bg += t * histogram[t]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_all - sum_bg) / weight_fg

        variance_between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        # `>=`, а не `>`: при бинаризации пиксель со значением ровно `t`
        # считается тёмным, только если `t < threshold`. На чётко бимодальном
        # изображении несколько соседних порогов подряд дают одинаковый
        # максимум дисперсии — предпочитая последний из них, а не первый, порог
        # уезжает к верхней границе диапазона, а не садится ровно на значение
        # тёмного кластера, где сам этот кластер ошибочно классифицировался бы
        # как светлый.
        if variance_between >= best_variance:
            best_variance = variance_between
            best_threshold = t

    return best_threshold


def binarize_otsu(image: Image.Image) -> Image.Image:
    """Бинаризует изображение по адаптивному порогу Оцу."""
    threshold = otsu_threshold(image)
    return image.point(lambda x: 0 if x < threshold else 255, mode="1").convert("L")
