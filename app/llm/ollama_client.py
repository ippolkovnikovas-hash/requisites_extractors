import json
import httpx
from loguru import logger

from app.config import settings
from app.llm.base import BaseLLMClient
from app.llm.prompts import get_prompt
from app.schemas.extraction import LLMExtractionResult
from app.core.exceptions import LLMError, LLMParseError


class OllamaClient(BaseLLMClient):

    def extract(self, text: str, prompt_version: str = "v1") -> LLMExtractionResult:
        prompt = get_prompt(prompt_version, text)
        url = f"{settings.ollama_base_url}/api/generate"
        logger.debug("Sending to Ollama", model=settings.ollama_model)

        try:
            resp = httpx.post(
                url,
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=settings.llm_timeout_seconds,
            )
            resp.raise_for_status()
        except Exception as e:
            raise LLMError(f"Ollama call failed: {e}")

        raw = resp.json().get("response", "")

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise LLMParseError(f"Cannot parse Ollama JSON: {e}", {"raw": raw})

        return LLMExtractionResult(
            raw_response=raw,
            parsed_data=parsed,
            model_name=settings.ollama_model,
            provider="ollama",
            prompt_version=prompt_version,
        )