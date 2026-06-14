"""
Схемы промежуточных результатов извлечения текста и LLM-ответа.
"""

from pydantic import BaseModel
from app.core.enums import ExtractorType


class TextExtractionResult(BaseModel):
    text: str
    extractor_used: ExtractorType
    pages: int | None = None
    ocr_used: bool = False
    warnings: list[str] = []


class NormalizedText(BaseModel):
    original_text: str
    normalized_text: str
    char_count_before: int
    char_count_after: int


class LLMExtractionResult(BaseModel):
    raw_response: str
    parsed_data: dict
    model_name: str
    provider: str
    prompt_version: str