"""
Модель реквизитов организации.

16 полей строго соответствуют плейсхолдерам shablon.docx.
to_template_dict() возвращает маппинг alias → значение для заполнения шаблона.
"""

from pydantic import BaseModel, Field


class RequisitesData(BaseModel):
    company_name:          str | None = Field(None, alias="FULL_ORG_NAME")
    short_name:            str | None = Field(None, alias="ORG_NAME")
    legal_address:         str | None = Field(None, alias="LEGAL_ADDRES")
    postal_address:        str | None = Field(None, alias="POST_ADDRES")
    ogrn:                  str | None = Field(None, alias="OGRN")
    inn:                   str | None = Field(None, alias="INN")
    kpp:                   str | None = Field(None, alias="KPP")
    bank_name:             str | None = Field(None, alias="BANK_NAME")
    checking_account:      str | None = Field(None, alias="RS")
    correspondent_account: str | None = Field(None, alias="KS")
    bik:                   str | None = Field(None, alias="BIK")
    ceo_position:          str | None = Field(None, alias="CEO_POSITION")
    ceo_fio_full:          str | None = Field(None, alias="CEO_FIO_FULL")
    ceo_fio:               str | None = Field(None, alias="CEO_FIO")
    phone:                 str | None = Field(None, alias="TEL")
    email:                 str | None = Field(None, alias="E-MAIL")

    model_config = {"populate_by_name": True}

    def to_template_dict(self) -> dict[str, str]:
        """Возвращает {alias: value} для заполнения shablon.docx."""
        aliases = {
            "company_name":          "FULL_ORG_NAME",
            "short_name":            "ORG_NAME",
            "legal_address":         "LEGAL_ADDRES",
            "postal_address":        "POST_ADDRES",
            "ogrn":                  "OGRN",
            "inn":                   "INN",
            "kpp":                   "KPP",
            "bank_name":             "BANK_NAME",
            "checking_account":      "RS",
            "correspondent_account": "KS",
            "bik":                   "BIK",
            "ceo_position":          "CEO_POSITION",
            "ceo_fio_full":          "CEO_FIO_FULL",
            "ceo_fio":               "CEO_FIO",
            "phone":                 "TEL",
            "email":                 "E-MAIL",
        }
        data = self.model_dump()
        return {alias: (data.get(field) or "") for field, alias in aliases.items()}

    def filled_fields(self) -> list[str]:
        return [k for k, v in self.model_dump().items() if v is not None]

    def missing_fields(self) -> list[str]:
        return [k for k, v in self.model_dump().items() if v is None]

    def fill_rate(self) -> float:
        filled = len(self.filled_fields())
        return round(filled / 16, 2)
