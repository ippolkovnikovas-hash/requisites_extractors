from pydantic import BaseModel

from app.schemas.requisites import RequisitesData


class FieldValidation(BaseModel):
    """
    Результат проверки одного поля. Контракт задан в CLAUDE.md:

    - `raw_value` — то, что пришло от пользователя или экстрактора. Никогда не
      изменяется и не скрывается: именно оно показывается в review-форме.
    - `normalized_value` — прозрачная нормализация (пробелы, регистр,
      однозначные OCR-подмены). Не подменяет `raw_value` в форме.
    - `is_missing` — значение не заполнено. Это НЕ то же самое, что заполненное
      неверно: отсутствие необязательного поля ошибкой не считается.
    - `reason` — жёсткая ошибка. Блокирует генерацию DOCX без `confirm_invalid`.
    - `warning` — показывается рядом с полем, но генерацию никогда не блокирует.
    """

    valid: bool
    is_missing: bool = False
    raw_value: str | None = None
    normalized_value: str | None = None
    reason: str | None = None
    warning: str | None = None


class ValidationReport(BaseModel):
    """
    Результат проверки всех 16 полей реквизитов.

    Три потока разведены намеренно:

    - `errors` — только жёсткие ошибки. Именно они блокируют `/generate` без
      `confirm_invalid`.
    - `warnings` — всё, что стоит показать рядом с полем, но что генерацию
      никогда не блокирует (контрольный ключ, нетипичный префикс, кросс-связи).
    - `review_reasons` — читаемые формулировки для человека: почему форму надо
      просмотреть глазами.

    `needs_review` (возвращается отдельно) поднимается и от ошибок, и от
    предупреждений: «посмотреть глазами» — это не то же самое, что
    «заблокировать».
    """

    # Все 16 полей RequisitesData
    company_name:          FieldValidation | None = None
    short_name:            FieldValidation | None = None
    legal_address:         FieldValidation | None = None
    postal_address:        FieldValidation | None = None
    ogrn:                  FieldValidation | None = None
    inn:                   FieldValidation | None = None
    kpp:                   FieldValidation | None = None
    bank_name:             FieldValidation | None = None
    checking_account:      FieldValidation | None = None
    correspondent_account: FieldValidation | None = None
    bik:                   FieldValidation | None = None
    ceo_position:          FieldValidation | None = None
    ceo_fio_full:          FieldValidation | None = None
    ceo_fio:               FieldValidation | None = None
    phone:                 FieldValidation | None = None
    email:                 FieldValidation | None = None

    cross_checks:          list[str] = []
    errors:                list[str] = []
    warnings:              list[str] = []
    review_reasons:        list[str] = []

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
