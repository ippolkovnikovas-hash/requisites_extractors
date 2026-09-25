"""
YandexGPT через OpenAI-совместимый API Yandex AI Studio.

base_url: https://ai.api.cloud.yandex.net/v1, project = ID каталога,
model: gpt://<folder_id>/<YANDEX_GPT_MODEL>. Ответ — JSON по схеме (response_format=json_schema).
Данные остаются в РФ; x-data-logging-enabled=false — Yandex не сохраняет запросы.
"""

import json
import re

from loguru import logger
from openai import OpenAI

from app.config import settings
from app.core.exceptions import LLMError, LLMParseError
from app.llm.base import BaseLLMClient
from app.llm.prompts import get_prompt
from app.schemas.extraction import LLMExtractionResult
from app.schemas.requisites import RequisitesData

_BASE_URL = "https://ai.api.cloud.yandex.net/v1"
_FIELDS = list(RequisitesData.model_fields.keys())

# Пустая строка = поле не найдено (строковые поля проще для structured output, чем null)
_JSON_SCHEMA = {
    "name": "requisites",
    "schema": {
        "type": "object",
        "properties": {f: {"type": "string"} for f in _FIELDS},
        "required": _FIELDS,
    },
}


def _parse_json(raw: str) -> dict:
    """JSON из ответа модели; допускает обёртку ```json ... ``` и текст вокруг."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


class YandexGPTClient(BaseLLMClient):

    def __init__(self) -> None:
        if not settings.yandex_api_key or not settings.yandex_folder_id:
            raise LLMError("LLM_PROVIDER=yandex requires YANDEX_API_KEY and YANDEX_FOLDER_ID")
        self._model = f"gpt://{settings.yandex_folder_id}/{settings.yandex_gpt_model}"
        self._client = OpenAI(
            api_key=settings.yandex_api_key,
            base_url=_BASE_URL,
            project=settings.yandex_folder_id,
            timeout=settings.llm_timeout_seconds,
            default_headers={
                "x-data-logging-enabled": "true" if settings.yandex_data_logging else "false",
            },
        )

    def _complete(self, prompt: str, structured: bool) -> str:
        kwargs = {}
        if structured:
            kwargs["response_format"] = {"type": "json_schema", "json_schema": _JSON_SCHEMA}
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    def extract(self, text: str, prompt_version: str = "v1") -> LLMExtractionResult:
        prompt = get_prompt(prompt_version, text)
        logger.debug("Sending to YandexGPT", model=settings.yandex_gpt_model, chars=len(text))

        try:
            raw = self._complete(prompt, structured=True)
        except Exception as e:
            # Не все модели поддерживают json_schema — повторяем без него
            logger.warning("YandexGPT structured call failed, retrying plain", reason=str(e))
            try:
                raw = self._complete(prompt, structured=False)
            except Exception as e2:
                raise LLMError(f"YandexGPT call failed: {e2}")

        try:
            parsed = _parse_json(raw)
        except json.JSONDecodeError as e:
            raise LLMParseError(f"Cannot parse YandexGPT JSON: {e}", {"raw": raw[:500]})

        # "" и "null" от модели → None, как у остальных провайдеров
        parsed = {
            k: (None if v in ("", "null", None) else v)
            for k, v in parsed.items()
            if k in _FIELDS
        }

        return LLMExtractionResult(
            raw_response=raw,
            parsed_data=parsed,
            model_name=settings.yandex_gpt_model,
            provider="yandex",
            prompt_version=prompt_version,
        )
