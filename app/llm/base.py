from abc import ABC, abstractmethod
from app.schemas.extraction import LLMExtractionResult


class BaseLLMClient(ABC):

    @abstractmethod
    def extract(self, text: str, prompt_version: str = "v1") -> LLMExtractionResult:
        """Send text to LLM, return structured result."""
        ...