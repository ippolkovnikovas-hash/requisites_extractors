"""
Перечисления (Enum) используемые во всём приложении.
"""

from enum import StrEnum


class DocumentType(StrEnum):
    DOCX      = "docx"
    DOC       = "doc"      # Word 97-2003, конвертация через LibreOffice
    ODT       = "odt"      # OpenDocument Text
    PDF_TEXT  = "pdf_text"   # цифровой PDF с текстовым слоем
    PDF_SCAN  = "pdf_scan"   # скан PDF — нужен OCR
    IMAGE     = "image"      # JPG / PNG / TIFF
    UNSUPPORTED = "unsupported"


class ExtractorType(StrEnum):
    PYTHON_DOCX = "python_docx"
    ODF         = "odf"
    LIBREOFFICE = "libreoffice"
    PDFPLUMBER  = "pdfplumber"
    TESSERACT   = "tesseract"
    EASYOCR     = "easyocr"
    YANDEX_VISION = "yandex_vision"


class LLMProvider(StrEnum):
    MOCK   = "mock"
    OPENAI = "openai"
    OLLAMA = "ollama"
    YANDEX = "yandex"


class ExportFormat(StrEnum):
    JSON = "json"
    XLSX = "xlsx"
    DOCX = "docx"
