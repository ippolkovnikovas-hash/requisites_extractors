from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from app.config import settings
from app.ocr import get_ocr_backend
from app.schemas.extraction import TextExtractionResult

# Фото с телефона обычно крупные; мелкие сканы увеличиваем — Tesseract лучше читает
_UPSCALE_BELOW_PX = 2500
# Основной проход (psm 6) и дополнительные: колонки (4) и разрозненный текст (11)
_MAIN_PSM = 6
_EXTRA_PSMS = (4, 11)


def _preprocess_image(image: Image.Image) -> Image.Image:
    """
    Без жёсткой бинаризации: на фото с неравномерным светом порог
    стирает цифры (замер: 18 → 44 найденных числовых поля из 60 на 10 фото).
    """
    image = ImageOps.exif_transpose(image).convert("L")
    w, h = image.size
    if max(w, h) < _UPSCALE_BELOW_PX:
        image = image.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
    image = ImageOps.autocontrast(image, cutoff=2)
    return image.filter(ImageFilter.SHARPEN)


def ocr_passes(backend, image: Image.Image) -> tuple[str, list[str]]:
    """Основной текст и дополнительные прочтения (если включены OCR_EXTRA_PASSES)."""
    main = "\n".join(backend.image_to_lines(image, psm=_MAIN_PSM)).strip()
    alts: list[str] = []
    if settings.ocr_extra_passes and backend.supports_psm:
        for psm in _EXTRA_PSMS:
            text = "\n".join(backend.image_to_lines(image, psm=psm)).strip()
            if text:
                alts.append(text)
    return main, alts


def extract_image_ocr(path: Path) -> TextExtractionResult:
    backend = get_ocr_backend()
    with Image.open(path) as source:
        image = _preprocess_image(source)
    text, alt_texts = ocr_passes(backend, image)
    return TextExtractionResult(
        text=text,
        extractor_used=backend.name(),
        ocr_used=True,
        pages=1,
        alt_texts=alt_texts,
    )
