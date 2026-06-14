"""
Схема входящего документа.
Создаётся в pipeline_service.run_pipeline() сразу после приёма файла.
"""

from pathlib import Path
from pydantic import BaseModel, Field
from app.core.enums import DocumentType


class DocumentInput(BaseModel):
    document_id: str
    original_filename: str
    extension: str                  # pdf | docx | jpg | png | tiff
    mime_type: str
    size_bytes: int
    storage_path: Path
    sha256: str
    doc_type: DocumentType = DocumentType.UNSUPPORTED

    model_config = {"arbitrary_types_allowed": True}