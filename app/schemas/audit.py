from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.technical import TechnicalFinding
from app.schemas.crawler import PageMetadata


class AuditCreateRequest(BaseModel):
    url: str = Field(..., json_schema_extra={"example": "https://example.com"}, description="Public URL to audit")


class AuditListItem(BaseModel):
    id: str
    url: str
    status: str
    score: int
    fetch_time_seconds: float
    created_at: datetime
    total_findings: int
    critical_count: int
    warning_count: int


class AuditHistoryResponse(BaseModel):
    total: int
    items: List[AuditListItem]


class AuditResponse(BaseModel):
    id: str
    url: str
    status: str
    score: int
    fetch_time_seconds: float
    error_message: Optional[str] = None
    created_at: datetime
    page_metadata: Optional[PageMetadata] = None
    findings: List[TechnicalFinding] = Field(default_factory=list)
    aeo_summary: Optional[Dict[str, Any]] = None
