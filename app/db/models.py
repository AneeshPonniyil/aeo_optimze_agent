import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Integer, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditRecord(Base):
    __tablename__ = "audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending, completed, failed
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetch_time_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Serialized JSON representations
    page_metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    aeo_summary_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    findings: Mapped[List["FindingRecord"]] = relationship(
        "FindingRecord",
        back_populates="audit",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class FindingRecord(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(String(36), ForeignKey("audits.id", ondelete="CASCADE"), nullable=False, index=True)
    
    check_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)  # critical, warning, info
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix: Mapped[str] = mapped_column(Text, nullable=False)
    is_llm_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    audit: Mapped["AuditRecord"] = relationship("AuditRecord", back_populates="findings")
