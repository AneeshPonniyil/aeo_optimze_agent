import logging
from typing import List
from app.config import settings
from app.core.llm.base import LLMProvider, LLMProviderError
from app.core.llm.mock_provider import MockLLMProvider
from app.core.llm.openai_provider import OpenAIProvider
from app.core.llm.gemini_provider import GeminiProvider
from app.schemas.crawler import FetchedPageContent
from app.schemas.technical import TechnicalFinding
from app.schemas.aeo import AEOCopilotResult

logger = logging.getLogger("zenvora.llm.engine")


class AEOCopilotEngine:
    """
    Orchestrator for AEO Copilot LLM providers with automatic schema validation,
    credential checking, and graceful fallback to MockLLMProvider upon API errors.
    """

    @classmethod
    def get_provider(cls) -> LLMProvider:
        provider_type = (settings.LLM_PROVIDER or "mock").lower()

        if provider_type == "openai":
            if settings.OPENAI_API_KEY:
                try:
                    return OpenAIProvider(api_key=settings.OPENAI_API_KEY)
                except Exception as e:
                    logger.warning(f"Could not initialize OpenAIProvider ({e}). Falling back to MockLLMProvider.")
            else:
                logger.info("OPENAI_API_KEY missing. Falling back to MockLLMProvider.")

        elif provider_type == "gemini":
            if settings.GEMINI_API_KEY:
                try:
                    return GeminiProvider(api_key=settings.GEMINI_API_KEY)
                except Exception as e:
                    logger.warning(f"Could not initialize GeminiProvider ({e}). Falling back to MockLLMProvider.")
            else:
                logger.info("GEMINI_API_KEY missing. Falling back to MockLLMProvider.")

        # Default fallback
        return MockLLMProvider()

    @classmethod
    async def analyze_page(
        cls,
        page_content: FetchedPageContent,
        technical_findings: List[TechnicalFinding],
    ) -> AEOCopilotResult:
        """
        Execute AEO recommendation generation with automatic fallback safety.
        """
        provider = cls.get_provider()
        try:
            return await provider.generate_aeo_recommendations(page_content, technical_findings)
        except Exception as e:
            logger.error(f"Selected LLM provider failed ({e}). Executing fallback to MockLLMProvider.")
            fallback = MockLLMProvider()
            return await fallback.generate_aeo_recommendations(page_content, technical_findings)
