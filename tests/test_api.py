from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

os.environ["RECONDESK_DATABASE_URL"] = "sqlite:///./data/recondesk-test.db"
Path("data/recondesk-test.db").unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.reconciliation import LedgerRow, reconcile  # noqa: E402


def test_dashboard_exposes_review_risk() -> None:
    with TestClient(app) as client:
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert body["runs"] == 3
        assert body["openExceptions"] == 4
        assert body["highRisk"] == 3
        assert body["latestMatchRate"] == 99.52


def test_reconciliation_applies_amount_and_date_tolerances() -> None:
    from datetime import date

    left = [LedgerRow("A-1", Decimal("100.00"), date(2026, 8, 1))]
    right = [LedgerRow("A-1", Decimal("100.40"), date(2026, 8, 2))]
    result = reconcile(left, right, Decimal("0.50"), 1)
    assert result.matched == 1
    assert result.differences == []


def test_csv_upload_creates_a_durable_exception_run() -> None:
    left = b"reference,amount,date,description\nT-1,100.00,2026-08-01,Order\nT-2,50.00,2026-08-01,Fee\n"
    right = b"reference,amount,date,description\nT-1,75.00,2026-08-01,Order\nT-2,50.00,2026-08-01,Fee\n"
    with TestClient(app) as client:
        response = client.post(
            "/api/reconcile",
            data={"name": "Automated upload test", "amount_tolerance": "0.50", "date_tolerance_days": "1"},
            files={"left_file": ("left.csv", left, "text/csv"), "right_file": ("right.csv", right, "text/csv")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["matchedRows"] == 1
        assert body["exceptionCount"] == 1
        exceptions = client.get(f"/api/runs/{body['id']}/exceptions").json()
        assert exceptions[0]["kind"] == "AMOUNT_MISMATCH"
        assert exceptions[0]["delta"] == 25.0


def test_resolve_action_is_idempotent() -> None:
    with TestClient(app) as client:
        item = client.get("/api/exceptions?status=OPEN").json()[0]
        before = client.get("/api/runs").json()
        target_before = next(run for run in before if run["id"] == item["runId"])["resolvedCount"]
        payload = {"actor": "QA Reviewer", "note": "Supporting document verified."}
        first = client.post(f"/api/exceptions/{item['id']}/resolve", json=payload)
        second = client.post(f"/api/exceptions/{item['id']}/resolve", json=payload)
        assert first.status_code == second.status_code == 200
        after = client.get("/api/runs").json()
        target_after = next(run for run in after if run["id"] == item["runId"])["resolvedCount"]
        assert target_after == target_before + 1


def test_export_has_a_stable_schema() -> None:
    with TestClient(app) as client:
        response = client.get("/api/export/exceptions.csv")
        assert response.status_code == 200
        assert response.text.startswith(
            "exception_id,run,reference,type,severity,status,left_amount,right_amount,delta,owner\n"
        )

