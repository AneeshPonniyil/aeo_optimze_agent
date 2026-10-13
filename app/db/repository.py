import json
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AuditRecord, FindingRecord

logger = logging.getLogger("zenvora.repository")


class AuditRepository:
    """
    Data access repository for Audit database operations.
    """

    @classmethod
    async def create_audit(cls, session: AsyncSession, url: str) -> AuditRecord:
        audit = AuditRecord(url=url, status="pending")
        session.add(audit)
        await session.flush()
        return audit

    @classmethod
    async def complete_audit(
        cls,
        session: AsyncSession,
        audit_id: str,
        score: int,
        fetch_time: float,
        page_metadata_dict: Dict[str, Any],
        findings_data: List[Dict[str, Any]],
        aeo_summary_dict: Optional[Dict[str, Any]] = None,
    ) -> Optional[AuditRecord]:
        result = await session.execute(select(AuditRecord).where(AuditRecord.id == audit_id))
        audit = result.scalar_one_or_none()
        if not audit:
            return None

        audit.status = "completed"
        audit.score = score
        audit.fetch_time_seconds = fetch_time
        audit.page_metadata_json = json.dumps(page_metadata_dict)
        if aeo_summary_dict:
            audit.aeo_summary_json = json.dumps(aeo_summary_dict)

        # Clear existing findings if re-run
        audit.findings.clear()

        # Add findings
        for f in findings_data:
            finding_rec = FindingRecord(
                audit_id=audit.id,
                check_id=f.get("check_id", "CUSTOM-CHECK"),
                category=f.get("category", "General"),
                title=f.get("title", ""),
                description=f.get("description", ""),
                severity=f.get("severity", "info"),
                evidence=f.get("evidence", ""),
                suggested_fix=f.get("suggested_fix", ""),
                is_llm_generated=f.get("is_llm_generated", False),
            )
            audit.findings.append(finding_rec)

        await session.flush()
        return audit

    @classmethod
    async def fail_audit(cls, session: AsyncSession, audit_id: str, error_message: str) -> Optional[AuditRecord]:
        result = await session.execute(select(AuditRecord).where(AuditRecord.id == audit_id))
        audit = result.scalar_one_or_none()
        if audit:
            audit.status = "failed"
            audit.error_message = error_message
            await session.flush()
        return audit

    @classmethod
    async def get_audit_by_id(cls, session: AsyncSession, audit_id: str) -> Optional[AuditRecord]:
        result = await session.execute(select(AuditRecord).where(AuditRecord.id == audit_id))
        return result.scalar_one_or_none()

    @classmethod
    async def list_audits(cls, session: AsyncSession, limit: int = 50, offset: int = 0) -> List[AuditRecord]:
        stmt = select(AuditRecord).order_by(desc(AuditRecord.created_at)).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def count_audits(cls, session: AsyncSession) -> int:
        stmt = select(func.count(AuditRecord.id))
        result = await session.execute(stmt)
        return result.scalar() or 0

    @classmethod
    async def delete_audit(cls, session: AsyncSession, audit_id: str) -> bool:
        audit = await cls.get_audit_by_id(session, audit_id)
        if audit:
            await session.delete(audit)
            await session.flush()
            return True
        return False
