import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repository import AuditRepository
from app.schemas.audit import AuditCreateRequest, AuditResponse
from app.schemas.technical import TechnicalFinding, SeverityEnum
from app.schemas.crawler import PageMetadata
from app.core.security import SSRFSecurityValidator, URLValidationError
from app.core.crawler import AsyncWebCrawler, CrawlerError
from app.core.analyzer import HTMLParserService, DeterministicTechnicalAnalyzer

logger = logging.getLogger("zenvora.api.audit")
router = APIRouter()


@router.post("/audits", response_model=AuditResponse, status_code=status.HTTP_201_CREATED, summary="Create and Execute Website Audit")
async def create_audit(payload: AuditCreateRequest, db: AsyncSession = Depends(get_db)):
    """
    Validate URL safety, fetch page content, perform deterministic technical & AEO analysis, and store results.
    """
    # 1. SSRF URL Security Validation
    try:
        normalized_url = await SSRFSecurityValidator.validate_and_normalize_url(payload.url)
    except URLValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 2. Initialize Audit record in DB
    audit = await AuditRepository.create_audit(db, url=normalized_url)

    # 3. Crawl Page
    crawler = AsyncWebCrawler()
    try:
        final_url, status_code, html_text, headers, fetch_time = await crawler.fetch_page(normalized_url, check_robots=True)
    except (CrawlerError, URLValidationError) as e:
        await AuditRepository.fail_audit(db, audit.id, error_message=str(e))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Crawl failed: {str(e)}")

    # 4. Parse HTML & Run Deterministic Technical Audit
    parsed_page = HTMLParserService.parse_html(
        target_url=final_url,
        status_code=status_code,
        html_text=html_text,
        headers=headers,
        fetch_time=fetch_time,
    )
    summary = DeterministicTechnicalAnalyzer.analyze(parsed_page)

    # 5. Run AEO Copilot AI Engine
    from app.core.llm.engine import AEOCopilotEngine
    aeo_result = await AEOCopilotEngine.analyze_page(parsed_page, summary.findings)
    aeo_dict = aeo_result.model_dump()

    # 6. Prepare data for DB persistence
    findings_data = [finding.model_dump() for finding in summary.findings]
    page_meta_dict = parsed_page.metadata.model_dump()

    updated_audit = await AuditRepository.complete_audit(
        session=db,
        audit_id=audit.id,
        score=summary.score,
        fetch_time=fetch_time,
        page_metadata_dict=page_meta_dict,
        findings_data=findings_data,
        aeo_summary_dict=aeo_dict,
    )

    # Convert to response model
    findings_list = [
        TechnicalFinding(
            check_id=f.check_id,
            category=f.category,
            title=f.title,
            description=f.description,
            severity=SeverityEnum(f.severity),
            evidence=f.evidence,
            suggested_fix=f.suggested_fix,
        )
        for f in updated_audit.findings
    ]

    return AuditResponse(
        id=updated_audit.id,
        url=updated_audit.url,
        status=updated_audit.status,
        score=updated_audit.score,
        fetch_time_seconds=updated_audit.fetch_time_seconds,
        created_at=updated_audit.created_at,
        page_metadata=parsed_page.metadata,
        findings=findings_list,
        aeo_summary=json.loads(updated_audit.aeo_summary_json) if updated_audit.aeo_summary_json else None,
    )


@router.get("/audits/{audit_id}", response_model=AuditResponse, summary="Get Audit by ID")
async def get_audit(audit_id: str, db: AsyncSession = Depends(get_db)):
    audit = await AuditRepository.get_audit_by_id(db, audit_id)
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit '{audit_id}' not found.")

    findings_list = [
        TechnicalFinding(
            check_id=f.check_id,
            category=f.category,
            title=f.title,
            description=f.description,
            severity=SeverityEnum(f.severity),
            evidence=f.evidence,
            suggested_fix=f.suggested_fix,
        )
        for f in audit.findings
    ]

    meta_obj = None
    if audit.page_metadata_json:
        meta_obj = PageMetadata(**json.loads(audit.page_metadata_json))

    return AuditResponse(
        id=audit.id,
        url=audit.url,
        status=audit.status,
        score=audit.score,
        fetch_time_seconds=audit.fetch_time_seconds,
        error_message=audit.error_message,
        created_at=audit.created_at,
        page_metadata=meta_obj,
        findings=findings_list,
        aeo_summary=json.loads(audit.aeo_summary_json) if audit.aeo_summary_json else None,
    )


@router.delete("/audits/{audit_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Audit Record")
async def delete_audit(audit_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await AuditRepository.delete_audit(db, audit_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit '{audit_id}' not found.")
    return None
