from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SeverityEnum(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class TechnicalFinding(BaseModel):
    check_id: str
    category: str  # e.g., "SEO", "AEO", "Accessibility", "Indexability"
    title: str
    description: str
    severity: SeverityEnum
    evidence: str
    suggested_fix: str


class TechnicalAuditSummary(BaseModel):
    score: int = Field(..., ge=0, le=100, description="Overall technical audit score out of 100")
    total_checks: int
    passed_checks: int
    critical_count: int
    warning_count: int
    info_count: int
    findings: List[TechnicalFinding] = Field(default_factory=list)
