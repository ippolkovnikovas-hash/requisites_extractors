import json

from loguru import logger
from openai import OpenAI

from app.config import settings
from app.core.exceptions import LLMError, LLMParseError
from app.llm.base import BaseLLMClient
from app.llm.prompts import get_prompt
from app.schemas.extraction import LLMExtractionResult


class OpenAIClient(BaseLLMClient):

    def __init__(self) -> None:
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.llm_timeout_seconds,
        )

    def extract(self, text: str, prompt_version: str = "v1") -> LLMExtractionResult:
        prompt = get_prompt(prompt_version, text)
        logger.debug("Sending to OpenAI", model=settings.llm_model, chars=len(text))

        try:
            response = self._client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise LLMError(f"OpenAI call failed: {e}")

        raw = response.choices[0].message.content or ""

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise LLMParseError(f"Cannot parse LLM JSON: {e}", {"raw": raw})

        return LLMExtractionResult(
            raw_response=raw,
            parsed_data=parsed,
            model_name=settings.llm_model,
            provider="openai",
            prompt_version=prompt_version,
        )
