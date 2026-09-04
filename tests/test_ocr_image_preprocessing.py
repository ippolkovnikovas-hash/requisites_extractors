"""
Тесты предобработки изображений для OCR: устранение мелкого наклона и
адаптивная бинаризация по методу Оцу.

Синтетические изображения — горизонтальные тёмные полосы на белом фоне —
имитируют строки текста для оценки наклона, без реального Tesseract.
"""

from PIL import Image, ImageDraw

from app.ocr.image_preprocessing import binarize_otsu, deskew, detect_skew_angle, otsu_threshold


def _striped_image(width: int = 240, height: int = 320) -> Image.Image:
    """Полосы имитируют строки текста: чёткий построчный профиль яркости."""
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    y = 10
    while y < height - 8:
        draw.rectangle([10, y, width - 10, y + 6], fill=0)
        y += 16
    return img


# ── detect_skew_angle ────────────────────────────────────────────────────────


def test_detect_skew_angle_is_near_zero_for_straight_image():
    angle = detect_skew_angle(_striped_image())
    assert abs(angle) <= 0.5


def test_detect_skew_angle_recovers_applied_rotation():
    """
    Изображение повёрнуто на +2° — метод должен найти угол коррекции,
    близкий к -2° (в допуске: наклон реального фото никогда не измеряется
    идеально точно, важна лишь достаточная для распознавания близость).
    """
    rotated = _striped_image().rotate(
        2.0, resample=Image.Resampling.BICUBIC, fillcolor=255
    )
    angle = detect_skew_angle(rotated)
    assert -3.0 <= angle <= -1.0


def test_detect_skew_angle_is_zero_for_blank_image():
    """
    Регрессия: на изображении без единого тёмного пикселя построчный профиль
    не меняется ни при каком угле поворота, и без явной защиты алгоритм
    возвращал бы первый перебранный угол — случайный поворот пустого кадра.
    """
    blank = Image.new("L", (240, 320), 255)
    assert detect_skew_angle(blank) == 0.0


def test_detect_skew_angle_handles_tiny_image_without_crashing():
    """Экстракторы вызывают предобработку и на нетипично маленьких сканах."""
    tiny = Image.new("L", (20, 20), 255)
    angle = detect_skew_angle(tiny)
    assert isinstance(angle, float)


# ── deskew ────────────────────────────────────────────────────────────────────


def test_deskew_straightens_rotated_image():
    rotated = _striped_image().rotate(
        2.0, resample=Image.Resampling.BICUBIC, fillcolor=255
    )
    fixed = deskew(rotated)
    residual = detect_skew_angle(fixed)
    assert abs(residual) <= 0.5


def test_deskew_is_noop_for_already_straight_image():
    """
    Уже выровненное изображение не должно проходить через лишний поворот —
    он всегда немного смазывает изображение ресемплингом, даже на нулевой
    угол.
    """
    img = _striped_image()
    assert deskew(img) is img


# ── otsu_threshold / binarize_otsu ──────────────────────────────────────────


def _bimodal_image() -> Image.Image:
    """Два чётких кластера яркости — тёмная и светлая половины."""
    img = Image.new("L", (100, 100), 0)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 49, 99], fill=30)
    draw.rectangle([50, 0, 99, 99], fill=220)
    return img


def test_otsu_threshold_splits_bimodal_histogram():
    threshold = otsu_threshold(_bimodal_image())
    assert 30 < threshold < 220


def test_otsu_threshold_handles_uniform_image_without_crashing():
    """
    Регрессия: на изображении с нулевой дисперсией (один цвет) перебор по
    гистограмме никогда не находит межклассовую дисперсию больше нуля —
    без защиты порог остался бы неинициализированным.
    """
    uniform = Image.new("L", (50, 50), 255)
    threshold = otsu_threshold(uniform)
    assert isinstance(threshold, int)
    assert 0 <= threshold <= 255


def test_binarize_otsu_produces_only_black_and_white():
    result = binarize_otsu(_bimodal_image())
    assert set(result.getdata()) <= {0, 255}


def test_binarize_otsu_returns_grayscale_mode():
    """Результат остаётся режима 'L' — тем же, что ждут остальные шаги
    предобработки (autocontrast, фильтры) в экстракторах."""
    result = binarize_otsu(_bimodal_image())
    assert result.mode == "L"
