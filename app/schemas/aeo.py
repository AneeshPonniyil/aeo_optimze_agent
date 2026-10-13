from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AEOSuggestion(BaseModel):
    check_id: str
    category: str = "AEO"
    title: str
    current_state_evidence: str
    suggested_aeo_content: str
    suggested_schema_code: Optional[str] = None
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence rating between 0.0 and 1.0")
    limitations: str = Field(..., description="Stated limitations or caveats regarding this recommendation")


class AEOCopilotResult(BaseModel):
    summary: str = Field(..., description="High-level executive summary of AEO readiness")
    entity_clarity_score: int = Field(..., ge=0, le=100, description="Score assessing how clearly AI search engines can identify the brand entity")
    answer_readiness_score: int = Field(..., ge=0, le=100, description="Score assessing how ready page content is for direct AI answer generation")
    key_recommendations: List[AEOSuggestion] = Field(default_factory=list)
    faq_opportunities: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Suggested Q&A pairs grounded in page content for FAQPage schema generation",
    )
    suggested_json_ld_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Complete suggested JSON-LD Schema.org code block generated for the page",
    )
