from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import AuditEvent, ReconciliationException, ReconciliationRun
from app.reconciliation import CsvValidationError, parse_csv, reconcile
from app.seed import seed_demo

MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def get_session():
    with SessionLocal() as session:
        yield session


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_demo(session)
    yield


app = FastAPI(
    title="Financial Data Reconciliation Engine",
    description="Automated transactional reconciliation and exception triage engine with root cause analysis (RCA) tracking and audit compliance.",
    version="1.0.0",
    lifespan=lifespan,
)


class ResolveCommand(BaseModel):
    actor: str = Field(min_length=2, max_length=80)
    note: str = Field(min_length=4, max_length=500)
    rca_category: str | None = Field(default="TIMING_DIFFERENCE", max_length=100)


def money(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def run_dto(run: ReconciliationRun) -> dict:
    return {
        "id": run.id,
        "name": run.name,
        "sourceLeft": run.source_left,
        "sourceRight": run.source_right,
        "leftRows": run.left_rows,
        "rightRows": run.right_rows,
        "matchedRows": run.matched_rows,
        "exceptionCount": run.exception_count,
        "resolvedCount": run.resolved_count,
        "matchRate": round(run.matched_rows / max(run.left_rows, run.right_rows) * 100, 2) if max(run.left_rows, run.right_rows) > 0 else 0,
        "totalLeft": money(run.total_left),
        "totalRight": money(run.total_right),
        "amountTolerance": money(run.amount_tolerance),
        "dateToleranceDays": run.date_tolerance_days,
        "status": run.status,
        "createdAt": run.created_at.isoformat(),
    }


def exception_dto(item: ReconciliationException) -> dict:
    return {
        "id": item.id,
        "runId": item.run_id,
        "runName": item.run.name,
        "reference": item.reference,
        "kind": item.kind,
        "severity": item.severity,
        "status": item.status,
        "rcaCategory": getattr(item, "rca_category", "UNCLASSIFIED"),
        "complianceStatus": getattr(item, "compliance_status", "PENDING_REVIEW"),
        "leftAmount": money(item.left_amount),
        "rightAmount": money(item.right_amount),
        "delta": money(item.delta),
        "leftDate": item.left_date,
        "rightDate": item.right_date,
        "owner": item.owner,
        "resolutionNote": item.resolution_note,
        "createdAt": item.created_at.isoformat(),
        "resolvedAt": item.resolved_at.isoformat() if item.resolved_at else None,
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "financial-reconciliation-api"}


@app.get("/api/dashboard")
def dashboard(session: Session = Depends(get_session)) -> dict:
    runs = session.scalars(select(ReconciliationRun).order_by(ReconciliationRun.created_at.desc())).all()
    open_items = session.scalar(select(func.count()).select_from(ReconciliationException).where(ReconciliationException.status == "OPEN")) or 0
    high_items = session.scalar(select(func.count()).select_from(ReconciliationException).where(ReconciliationException.status == "OPEN", ReconciliationException.severity == "HIGH")) or 0
    resolved = session.scalar(select(func.count()).select_from(ReconciliationException).where(ReconciliationException.status == "RESOLVED")) or 0
    latest = runs[0] if runs else None
    return {
        "runs": len(runs),
        "openExceptions": open_items,
        "highRisk": high_items,
        "resolved": resolved,
        "latestMatchRate": round(latest.matched_rows / max(latest.left_rows, latest.right_rows) * 100, 2) if (latest and max(latest.left_rows, latest.right_rows) > 0) else 0,
        "latestRun": run_dto(latest) if latest else None,
    }


@app.get("/api/runs")
def list_runs(session: Session = Depends(get_session)) -> list[dict]:
    return [run_dto(run) for run in session.scalars(select(ReconciliationRun).order_by(ReconciliationRun.created_at.desc())).all()]


@app.get("/api/exceptions")
def list_exceptions(status: str | None = None, session: Session = Depends(get_session)) -> list[dict]:
    query = select(ReconciliationException).order_by(ReconciliationException.created_at.desc(), ReconciliationException.id.desc())
    if status:
        query = query.where(ReconciliationException.status == status.upper())
    return [exception_dto(item) for item in session.scalars(query).all()]


@app.get("/api/runs/{run_id}/exceptions")
def run_exceptions(run_id: int, session: Session = Depends(get_session)) -> list[dict]:
    return [exception_dto(item) for item in session.scalars(select(ReconciliationException).where(ReconciliationException.run_id == run_id).order_by(ReconciliationException.id)).all()]


@app.post("/api/exceptions/{exception_id}/resolve")
def resolve_exception(exception_id: int, command: ResolveCommand, session: Session = Depends(get_session)) -> dict:
    item = session.get(ReconciliationException, exception_id)
    if item is None:
        raise HTTPException(404, "Exception not found")
    if item.status == "RESOLVED":
        return exception_dto(item)
    
    item.status = "RESOLVED"
    item.owner = command.actor
    item.resolution_note = command.note
    if hasattr(item, "rca_category") and command.rca_category:
        item.rca_category = command.rca_category
    if hasattr(item, "compliance_status"):
        item.compliance_status = "AUDIT_CLEARED"
        
    item.resolved_at = datetime.now(UTC).replace(tzinfo=None)
    item.run.resolved_count += 1
    if item.run.resolved_count >= item.run.exception_count:
        item.run.status = "RECONCILED"
    session.add(AuditEvent(action="EXCEPTION_RESOLVED", actor=command.actor, detail=f"{item.reference} resolved via RCA [{command.rca_category or 'GENERAL'}]: {command.note}"))
    session.commit()
    return exception_dto(item)


@app.post("/api/exceptions/{exception_id}/reopen")
def reopen_exception(exception_id: int, session: Session = Depends(get_session)) -> dict:
    item = session.get(ReconciliationException, exception_id)
    if item is None:
        raise HTTPException(404, "Exception not found")
    if item.status == "OPEN":
        return exception_dto(item)
    
    item.status = "OPEN"
    item.resolved_at = None
    if hasattr(item, "compliance_status"):
        item.compliance_status = "UNDER_REVIEW"
    item.run.resolved_count = max(0, item.run.resolved_count - 1)
    item.run.status = "NEEDS_REVIEW"
    session.add(AuditEvent(action="EXCEPTION_REOPENED", actor="Compliance Auditor", detail=f"{item.reference} reopened for root cause review."))
    session.commit()
    return exception_dto(item)


@app.post("/api/reconcile")
async def create_reconciliation(
    name: str = Form(..., min_length=3, max_length=160),
    amount_tolerance: str = Form("0.01"),
    date_tolerance_days: int = Form(0, ge=0, le=31),
    left_file: UploadFile = File(...),
    right_file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    left_content = await left_file.read(MAX_UPLOAD_BYTES + 1)
    right_content = await right_file.read(MAX_UPLOAD_BYTES + 1)
    if len(left_content) > MAX_UPLOAD_BYTES or len(right_content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Each CSV must be 2 MB or smaller")
    try:
        tolerance = Decimal(amount_tolerance).quantize(Decimal("0.01"))
        if tolerance < 0:
            raise InvalidOperation
        left_rows = parse_csv(left_content)
        right_rows = parse_csv(right_content)
    except (InvalidOperation, CsvValidationError) as exc:
        raise HTTPException(422, str(exc) or "Invalid amount tolerance") from exc

    result = reconcile(left_rows, right_rows, tolerance, date_tolerance_days)
    run = ReconciliationRun(
        name=name,
        source_left=left_file.filename or "internal_ledger.csv",
        source_right=right_file.filename or "external_statement.csv",
        left_rows=len(left_rows),
        right_rows=len(right_rows),
        matched_rows=result.matched,
        exception_count=len(result.differences),
        resolved_count=0,
        total_left=result.total_left,
        total_right=result.total_right,
        amount_tolerance=tolerance,
        date_tolerance_days=date_tolerance_days,
        status="RECONCILED" if not result.differences else "NEEDS_REVIEW",
    )
    session.add(run)
    session.flush()
    for diff in result.differences:
        # Default RCA category based on difference kind
        rca_cat = "TIMING_DIFFERENCE" if diff.kind == "DATE_MISMATCH" else ("FEE_VARIANCE" if diff.kind == "AMOUNT_MISMATCH" else "MISSING_RECORD")
        session.add(ReconciliationException(
            run_id=run.id,
            reference=diff.reference,
            kind=diff.kind,
            severity=diff.severity,
            left_amount=diff.left.amount if diff.left else None,
            right_amount=diff.right.amount if diff.right else None,
            delta=diff.delta,
            left_date=diff.left.date.isoformat() if diff.left else None,
            right_date=diff.right.date.isoformat() if diff.right else None,
            owner="Unassigned",
            rca_category=rca_cat,
            compliance_status="PENDING_REVIEW",
        ))
    session.add(AuditEvent(action="RUN_COMPLETED", actor="reconciliation-engine", detail=f"{name} processed with {len(result.differences)} flagged exceptions."))
    session.commit()
    return run_dto(run)


@app.get("/api/audit")
def audit(session: Session = Depends(get_session)) -> list[dict]:
    return [{"id": item.id, "action": item.action, "actor": item.actor, "detail": item.detail, "createdAt": item.created_at.isoformat()} for item in session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(30)).all()]


@app.get("/api/export/exceptions.csv")
def export_exceptions(session: Session = Depends(get_session)) -> Response:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["exception_id", "run", "reference", "type", "severity", "status", "rca_category", "compliance_status", "left_amount", "right_amount", "delta", "owner"])
    for item in session.scalars(select(ReconciliationException).order_by(ReconciliationException.id)).all():
        writer.writerow([
            item.id,
            item.run.name,
            item.reference,
            item.kind,
            item.severity,
            item.status,
            getattr(item, "rca_category", "UNCLASSIFIED"),
            getattr(item, "compliance_status", "PENDING_REVIEW"),
            item.left_amount or "",
            item.right_amount or "",
            item.delta if item.delta is not None else "",
            item.owner or "",
        ])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=reconciliation-audit-report.csv"})


STATIC = Path(__file__).resolve().parents[1] / "static"
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")