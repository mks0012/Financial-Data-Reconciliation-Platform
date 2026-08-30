from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, ReconciliationException, ReconciliationRun


def seed_demo(session: Session) -> None:
    if session.scalar(select(ReconciliationRun.id).limit(1)) is not None:
        return

    now = datetime.now(UTC).replace(tzinfo=None)
    runs = [
        ReconciliationRun(
            name="July payment settlement",
            source_left="gateway_july.csv",
            source_right="bank_july.csv",
            left_rows=1248,
            right_rows=1247,
            matched_rows=1242,
            exception_count=6,
            resolved_count=2,
            total_left=Decimal("428731.82"),
            total_right=Decimal("428109.82"),
            amount_tolerance=Decimal("0.50"),
            date_tolerance_days=1,
            status="NEEDS_REVIEW",
            created_at=now - timedelta(minutes=22),
        ),
        ReconciliationRun(
            name="Marketplace settlements W31",
            source_left="orders_w31.csv",
            source_right="settlements_w31.csv",
            left_rows=842,
            right_rows=842,
            matched_rows=837,
            exception_count=5,
            resolved_count=5,
            total_left=Decimal("186440.17"),
            total_right=Decimal("186440.17"),
            amount_tolerance=Decimal("0.01"),
            date_tolerance_days=2,
            status="RECONCILED",
            created_at=now - timedelta(days=1, hours=3),
        ),
        ReconciliationRun(
            name="Corporate card controls",
            source_left="cards_july.csv",
            source_right="ledger_july.csv",
            left_rows=391,
            right_rows=389,
            matched_rows=384,
            exception_count=7,
            resolved_count=4,
            total_left=Decimal("94725.54"),
            total_right=Decimal("94312.09"),
            amount_tolerance=Decimal("1.00"),
            date_tolerance_days=1,
            status="NEEDS_REVIEW",
            created_at=now - timedelta(days=2, hours=6),
        ),
    ]
    session.add_all(runs)
    session.flush()

    current = runs[0]
    exceptions = [
        ReconciliationException(run_id=current.id, reference="PAY-88421", kind="AMOUNT_MISMATCH", severity="HIGH", status="OPEN", left_amount=Decimal("1498.00"), right_amount=Decimal("1198.00"), delta=Decimal("300.00"), left_date="2026-07-31", right_date="2026-07-31", owner="Unassigned", created_at=now - timedelta(minutes=22)),
        ReconciliationException(run_id=current.id, reference="PAY-88477", kind="MISSING_RIGHT", severity="HIGH", status="OPEN", left_amount=Decimal("219.50"), right_amount=None, delta=None, left_date="2026-07-31", right_date=None, owner="Unassigned", created_at=now - timedelta(minutes=22)),
        ReconciliationException(run_id=current.id, reference="PAY-88502", kind="DATE_MISMATCH", severity="LOW", status="OPEN", left_amount=Decimal("84.29"), right_amount=Decimal("84.29"), delta=Decimal("0.00"), left_date="2026-07-29", right_date="2026-08-01", owner="Alex Chen", created_at=now - timedelta(minutes=22)),
        ReconciliationException(run_id=current.id, reference="PAY-88518", kind="DUPLICATE_KEY", severity="HIGH", status="OPEN", left_amount=Decimal("156.90"), right_amount=Decimal("156.90"), delta=Decimal("0.00"), left_date="2026-07-31", right_date="2026-07-31", owner="Alex Chen", created_at=now - timedelta(minutes=22)),
        ReconciliationException(run_id=current.id, reference="PAY-88310", kind="AMOUNT_MISMATCH", severity="MEDIUM", status="RESOLVED", left_amount=Decimal("921.14"), right_amount=Decimal("899.14"), delta=Decimal("22.00"), left_date="2026-07-30", right_date="2026-07-30", owner="Maya Patel", resolution_note="Bank fee booked separately; supporting entry verified.", resolved_at=now - timedelta(minutes=8), created_at=now - timedelta(minutes=22)),
        ReconciliationException(run_id=current.id, reference="PAY-88294", kind="MISSING_LEFT", severity="HIGH", status="RESOLVED", left_amount=None, right_amount=Decimal("322.00"), delta=None, left_date=None, right_date="2026-07-30", owner="Maya Patel", resolution_note="Late gateway posting confirmed for next settlement window.", resolved_at=now - timedelta(minutes=5), created_at=now - timedelta(minutes=22)),
    ]
    session.add_all(exceptions)
    session.add_all([
        AuditEvent(action="RUN_COMPLETED", actor="reconciliation-worker", detail="July payment settlement produced 6 exceptions.", created_at=now - timedelta(minutes=22)),
        AuditEvent(action="EXCEPTION_ASSIGNED", actor="Alex Chen", detail="PAY-88518 assigned for duplicate investigation.", created_at=now - timedelta(minutes=14)),
        AuditEvent(action="EXCEPTION_RESOLVED", actor="Maya Patel", detail="PAY-88310 resolved with supporting note.", created_at=now - timedelta(minutes=8)),
        AuditEvent(action="EXCEPTION_RESOLVED", actor="Maya Patel", detail="PAY-88294 moved to next settlement window.", created_at=now - timedelta(minutes=5)),
    ])
    session.commit()
