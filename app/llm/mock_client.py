"""
Mock LLM — для отладки pipeline без реального провайдера.
Все 16 полей строго соответствуют RequisitesData и shablon.docx.

Удалены:  ceo_name, document_date, document_number
Добавлены: ceo_position, ceo_fio_full, ceo_fio
"""

import json
from app.llm.base import BaseLLMClient
from app.schemas.extraction import LLMExtractionResult

# Ключи совпадают с python-именами полей RequisitesData (populate_by_name=True)
_EMPTY_RESPONSE: dict[str, None] = {
    # --- Идентификация организации ---
    "company_name":          None,  # FULL_ORG_NAME
    "short_name":            None,  # ORG_NAME

    # --- Адреса ---
    "legal_address":         None,  # LEGAL_ADDRES
    "postal_address":        None,  # POST_ADDRES

    # --- Регистрационные данные ---
    "ogrn":                  None,  # OGRN
    "inn":                   None,  # INN
    "kpp":                   None,  # KPP

    # --- Банковские реквизиты ---
    "bank_name":             None,  # BANK_NAME
    "checking_account":      None,  # RS
    "correspondent_account": None,  # KS
    "bik":                   None,  # BIK

    # --- Руководитель ---
    "ceo_position":          None,  # CEO_POSITION
    "ceo_fio_full":          None,  # CEO_FIO_FULL
    "ceo_fio":               None,  # CEO_FIO

    # --- Контакты ---
    "phone":                 None,  # TEL
    "email":                 None,  # E-MAIL
}


class MockLLMClient(BaseLLMClient):

    def extract(self, text: str, prompt_version: str = "v1") -> LLMExtractionResult:
        raw = json.dumps(_EMPTY_RESPONSE, ensure_ascii=False, indent=2)
        return LLMExtractionResult(
            raw_response=raw,
            parsed_data=_EMPTY_RESPONSE.copy(),
            model_name="mock",
            provider="mock",
            prompt_version=prompt_version,
        )