"""
Перечисления (Enum) используемые во всём приложении.
"""

from enum import StrEnum


class DocumentType(StrEnum):
    DOCX      = "docx"
    PDF_TEXT  = "pdf_text"   # цифровой PDF с текстовым слоем
    PDF_SCAN  = "pdf_scan"   # скан PDF — нужен OCR
    IMAGE     = "image"      # JPG / PNG / TIFF
    UNSUPPORTED = "unsupported"


class ExtractorType(StrEnum):
    PYTHON_DOCX = "python_docx"
    PDFPLUMBER  = "pdfplumber"
    TESSERACT   = "tesseract"
    EASYOCR     = "easyocr"


class LLMProvider(StrEnum):
    MOCK   = "mock"
    OPENAI = "openai"
    OLLAMA = "ollama"


class ExportFormat(StrEnum):
    JSON = "json"
    XLSX = "xlsx"
    DOCX = "docx"