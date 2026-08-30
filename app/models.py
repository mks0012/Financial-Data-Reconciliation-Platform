from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    source_left: Mapped[str] = mapped_column(String(120))
    source_right: Mapped[str] = mapped_column(String(120))
    left_rows: Mapped[int]
    right_rows: Mapped[int]
    matched_rows: Mapped[int]
    exception_count: Mapped[int]
    resolved_count: Mapped[int] = mapped_column(default=0)
    total_left: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    total_right: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    amount_tolerance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.01"))
    date_tolerance_days: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(30), default="COMPLETED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    exceptions: Mapped[list["ReconciliationException"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ReconciliationException(Base):
    __tablename__ = "reconciliation_exceptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("reconciliation_runs.id"), index=True)
    reference: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    
    # NEW RCA AND COMPLIANCE FIELDS
    rca_category: Mapped[str | None] = mapped_column(String(100), default="UNCLASSIFIED", nullable=True)
    compliance_status: Mapped[str] = mapped_column(String(50), default="PENDING_REVIEW")
    
    left_amount: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    right_amount: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    delta: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    left_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    right_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    run: Mapped[ReconciliationRun] = relationship(back_populates="exceptions")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(50))
    actor: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)