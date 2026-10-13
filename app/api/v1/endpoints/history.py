from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.repository import AuditRepository
from app.schemas.audit import AuditHistoryResponse, AuditListItem

router = APIRouter()


@router.get("/audits", response_model=AuditHistoryResponse, summary="List Past Audits History")
async def list_audits(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    audits = await AuditRepository.list_audits(db, limit=limit, offset=offset)
    total = await AuditRepository.count_audits(db)

    items = []
    for a in audits:
        total_findings = len(a.findings)
        critical_count = sum(1 for f in a.findings if f.severity == "critical")
        warning_count = sum(1 for f in a.findings if f.severity == "warning")

        items.append(
            AuditListItem(
                id=a.id,
                url=a.url,
                status=a.status,
                score=a.score,
                fetch_time_seconds=a.fetch_time_seconds,
                created_at=a.created_at,
                total_findings=total_findings,
                critical_count=critical_count,
                warning_count=warning_count,
            )
        )

    return AuditHistoryResponse(total=total, items=items)
