import json
import logging
from typing import List
import httpx

from app.config import settings
from app.core.llm.base import LLMProvider, LLMProviderError
from app.schemas.crawler import FetchedPageContent
from app.schemas.technical import TechnicalFinding
from app.schemas.aeo import AEOCopilotResult

logger = logging.getLogger("zenvora.llm.gemini")


class GeminiProvider(LLMProvider):
    """
    Google Gemini LLM provider integration producing schema-validated AEO analysis.
    """

    def __init__(self, api_key: str = settings.GEMINI_API_KEY, model: str = "gemini-1.5-flash"):
        if not api_key:
            raise LLMProviderError("GEMINI_API_KEY is not configured in environment variables.")
        self.api_key = api_key
        self.model = model

    async def generate_aeo_recommendations(
        self,
        page_content: FetchedPageContent,
        technical_findings: List[TechnicalFinding],
    ) -> AEOCopilotResult:
        prompt_data = {
            "url": page_content.url,
            "title": page_content.metadata.title,
            "meta_description": page_content.metadata.meta_description,
            "h1_headings": page_content.headings.h1_list,
            "h2_headings": page_content.headings.h2_list,
            "word_count": page_content.word_count,
            "schema_types": page_content.structured_data.schema_types,
            "technical_issues": [f.model_dump() for f in technical_findings],
            "body_excerpt": page_content.text_content[:1500],
        }

        system_instruction = (
            "You are Zenvora AI Website & AEO Audit Copilot. "
            "Analyze page evidence to output grounded Answer Engine Optimization (AEO) recommendations. "
            "Respond strictly in valid JSON format matching AEOCopilotResult model."
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": f"{system_instruction}\n\nEvidence JSON:\n{json.dumps(prompt_data)}"}]
            }],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    raise LLMProviderError(f"Gemini API returned status {response.status_code}: {response.text}")
                
                res_data = response.json()
                raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return AEOCopilotResult.model_validate_json(raw_text)
        except Exception as e:
            logger.error(f"Gemini provider execution failed: {e}")
            raise LLMProviderError(f"Gemini generation failed: {str(e)}")
