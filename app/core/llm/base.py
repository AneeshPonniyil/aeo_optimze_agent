from abc import ABC, abstractmethod
from typing import List
from app.schemas.crawler import FetchedPageContent
from app.schemas.technical import TechnicalFinding
from app.schemas.aeo import AEOCopilotResult


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMProvider(ABC):
    """
    Abstract Base Class for LLM Provider implementations.
    """

    @abstractmethod
    async def generate_aeo_recommendations(
        self,
        page_content: FetchedPageContent,
        technical_findings: List[TechnicalFinding],
    ) -> AEOCopilotResult:
        """
        Generate grounded Answer Engine Optimization (AEO) recommendations based on page evidence.
        Must return a validated AEOCopilotResult instance.
        """
        pass
