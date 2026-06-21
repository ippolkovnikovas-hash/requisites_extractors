from pydantic import BaseModel

from app.schemas.requisites import RequisitesData


class FieldValidation(BaseModel):
    valid: bool
    value: str | None = None
    reason: str | None = None


class ValidationReport(BaseModel):
    inn:                   FieldValidation | None = None
    kpp:                   FieldValidation | None = None
    ogrn:                  FieldValidation | None = None
    bik:                   FieldValidation | None = None
    checking_account:      FieldValidation | None = None
    correspondent_account: FieldValidation | None = None
    cross_checks:          list[str] = []
    errors:                list[str] = []

    model_config = {"arbitrary_types_allowed": True}


class PipelineResult(BaseModel):
    document_id: str
    original_filename: str
    data: RequisitesData
    validation: ValidationReport
    needs_review: bool
    warnings: list[str] = []
    status: str
    fill_rate: float
    raw_text_path: str | None = None
    json_path: str | None = None
    xlsx_path: str | None = None
    docx_path: str | None = None
    processing_meta: dict = {}
