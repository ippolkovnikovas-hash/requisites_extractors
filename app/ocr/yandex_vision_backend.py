"""
OCR через Yandex Vision OCR (AI Studio), REST API v1.

POST https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText
Заголовки: Authorization: Api-Key <ключ>, x-folder-id, x-data-logging-enabled.
Ответ: {"result": {"textAnnotation": {"fullText": ..., "blocks": [{"lines": [{"text"}]}]}}}

Облаку отдаём исходное цветное изображение: предобработка под Tesseract
(контраст, резкость) нейросетевому OCR только мешает.
"""

import base64
import io

import httpx
from loguru import logger
from PIL import Image

from app.config import settings
from app.core.enums import ExtractorType
from app.core.exceptions import TextExtractionError
from app.ocr.base import OcrBackend

_URL = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText"
# Ограничение API — не больше 20 млн пикселей; берём с запасом
_MAX_PIXELS = 18_000_000
# Лимит размера файла у API ~10 МБ; JPEG 90 для фото обычно 1–4 МБ
_JPEG_QUALITY = 90


def _encode_image(image: Image.Image) -> str:
    image = image.convert("RGB")
    w, h = image.size
    if w * h > _MAX_PIXELS:
        scale = (_MAX_PIXELS / (w * h)) ** 0.5
        image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _lines_from_response(payload: dict) -> list[str]:
    annotation = (payload.get("result") or payload).get("textAnnotation") or {}
    lines = [
        line.get("text", "").strip()
        for block in annotation.get("blocks", [])
        for line in block.get("lines", [])
    ]
    lines = [line for line in lines if line]
    if not lines and annotation.get("fullText"):
        lines = [line.strip() for line in annotation["fullText"].splitlines() if line.strip()]
    return lines


class YandexVisionBackend(OcrBackend):
    # Предобработка под Tesseract не нужна — отдаём исходное изображение
    needs_preprocessing = False

    def __init__(self) -> None:
        if not settings.yandex_api_key or not settings.yandex_folder_id:
            raise TextExtractionError(
                "OCR_BACKEND=yandex requires YANDEX_API_KEY and YANDEX_FOLDER_ID in .env"
            )

    def image_to_lines(
        self, image: Image.Image, lang: str = "rus+eng", psm: int = 6
    ) -> list[str]:
        body = {
            "mimeType": "JPEG",
            "languageCodes": ["ru", "en"],
            "model": settings.yandex_ocr_model,
            "content": _encode_image(image),
        }
        headers = {
            "Authorization": f"Api-Key {settings.yandex_api_key}",
            "x-folder-id": settings.yandex_folder_id,
            "x-data-logging-enabled": "true" if settings.yandex_data_logging else "false",
        }
        try:
            resp = httpx.post(_URL, json=body, headers=headers, timeout=settings.llm_timeout_seconds)
        except httpx.HTTPError as e:
            raise TextExtractionError(f"Yandex Vision request failed: {type(e).__name__}")
        if resp.status_code != 200:
            # Текст ответа не логируем целиком: там может быть эхо запроса
            raise TextExtractionError(
                f"Yandex Vision error: HTTP {resp.status_code}",
                {"body": resp.text[:300]},
            )
        lines = _lines_from_response(resp.json())
        logger.debug("Yandex Vision OCR done", lines=len(lines))
        return lines

    def image_to_text(self, image: Image.Image, lang: str = "rus+eng") -> str:
        return "\n".join(self.image_to_lines(image, lang))

    def name(self) -> str:
        return ExtractorType.YANDEX_VISION
