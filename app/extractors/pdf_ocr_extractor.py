import tempfile
from pathlib import Path

from loguru import logger
from pdf2image import convert_from_path
from PIL import Image, ImageFilter, ImageOps

from app.config import settings
from app.core.exceptions import TextExtractionError
from app.extractors.image_ocr_extractor import ocr_passes
from app.ocr import get_ocr_backend
from app.schemas.extraction import TextExtractionResult


def _preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    image = ImageOps.autocontrast(image, cutoff=2)
    image = image.filter(ImageFilter.SHARPEN)
    return image


_RENDER_DPI = 300


def _render_with_pdfium(path: Path) -> list[Image.Image]:
    """Рендер страниц через pypdfium2 (зависимость pdfplumber) — не требует Poppler."""
    import pypdfium2

    pdf = pypdfium2.PdfDocument(str(path))
    try:
        return [page.render(scale=_RENDER_DPI / 72).to_pil() for page in pdf]
    finally:
        pdf.close()


def _render_pages(path: Path, tmp_dir: str, warnings: list[str]) -> list[Image.Image]:
    try:
        return convert_from_path(
            str(path), dpi=_RENDER_DPI, fmt="png",
            output_folder=tmp_dir,
            poppler_path=settings.poppler_path or None,
        )
    except Exception as e:
        logger.warning("Poppler render failed, falling back to pypdfium2", reason=str(e))
        warnings.append("Poppler unavailable — pages rendered with pypdfium2")
        return _render_with_pdfium(path)


def extract_pdf_ocr(path: Path) -> TextExtractionResult:
    backend = get_ocr_backend()
    warnings: list[str] = []
    pages_text: list[str] = []
    alt_pages: list[list[str]] = []
    total_pages = 0

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            images = _render_pages(path, tmp_dir, warnings)
            total_pages = len(images)

            for page_num, image in enumerate(images, start=1):
                try:
                    processed = _preprocess_image(image)
                    text, alts = ocr_passes(backend, processed)
                    for idx, alt in enumerate(alts):
                        if len(alt_pages) <= idx:
                            alt_pages.append([])
                        alt_pages[idx].append(alt)
                    if text:
                        pages_text.append(f"[Страница {page_num}]\n{text}")
                    else:
                        warnings.append(f"Page {page_num}: OCR returned empty text")
                except Exception as e:
                    warnings.append(f"Page {page_num}: OCR failed — {e}")

    except Exception as e:
        raise TextExtractionError(f"Cannot OCR PDF: {e}", {"path": str(path)})

    full_text = "\n\n".join(pages_text)
    logger.info("PDF OCR done", path=path.name, pages=total_pages, chars=len(full_text))

    return TextExtractionResult(
        text=full_text,
        extractor_used=backend.name(),
        ocr_used=True,
        pages=total_pages,
        warnings=warnings,
        alt_texts=["\n\n".join(pages) for pages in alt_pages],
    )
