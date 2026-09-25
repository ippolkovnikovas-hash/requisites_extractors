from dataclasses import dataclass, field


@dataclass
class HealthResponse:
    status: str = "ok"
    version: str = "1.0.0"


@dataclass
class ExtractResponse:
    document_id: str
    status: str
    needs_review: bool
    fill_rate: float
    data: dict
    validation: dict
    extracted_by: list
    processing_meta: dict
    warnings: list
    json_path: str
    xlsx_path: str
    docx_path: str | None = None


@dataclass
class ErrorResponse:
    error: str
    code: int
    details: str = ""
