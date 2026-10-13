import json
import logging
from typing import List
import httpx

from app.config import settings
from app.core.llm.base import LLMProvider, LLMProviderError
from app.schemas.crawler import FetchedPageContent
from app.schemas.technical import TechnicalFinding
from app.schemas.aeo import AEOCopilotResult

logger = logging.getLogger("zenvora.llm.openai")


class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM provider integration producing schema-validated AEO analysis.
    """

    def __init__(self, api_key: str = settings.OPENAI_API_KEY, model: str = "gpt-4o-mini"):
        if not api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured in environment variables.")
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

        system_prompt = """You are Zenvora AI Website & AEO Audit Copilot.
Your job is to analyze the provided web page evidence and technical issues to output Answer Engine Optimization (AEO) recommendations.
CRITICAL MANDATES:
1. Base all judgments strictly on the provided page content and evidence. Never fabricate information.
2. Emit ONLY valid JSON matching the following schema structure:
{
  "summary": "string",
  "entity_clarity_score": integer_0_to_100,
  "answer_readiness_score": integer_0_to_100,
  "key_recommendations": [
    {
      "check_id": "string",
      "category": "string",
      "title": "string",
      "current_state_evidence": "string",
      "suggested_aeo_content": "string",
      "suggested_schema_code": "optional_string",
      "confidence_score": float_0_to_1,
      "limitations": "string"
    }
  ],
  "faq_opportunities": [{"question": "string", "answer": "string"}],
  "suggested_json_ld_schema": dict_or_null
}"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(prompt_data)},
            ],
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                if response.status_code != 200:
                    raise LLMProviderError(f"OpenAI API returned status {response.status_code}: {response.text}")
                
                res_data = response.json()
                content = res_data["choices"][0]["message"]["content"]
                return AEOCopilotResult.model_validate_json(content)
        except Exception as e:
            logger.error(f"OpenAI provider execution failed: {e}")
            raise LLMProviderError(f"OpenAI completion failed: {str(e)}")
