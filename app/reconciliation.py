from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = {"reference", "amount", "date"}


class CsvValidationError(ValueError):
    pass


@dataclass(frozen=True)
class LedgerRow:
    reference: str
    amount: Decimal
    date: date
    description: str = ""


@dataclass(frozen=True)
class Difference:
    reference: str
    kind: str
    severity: str
    left: LedgerRow | None
    right: LedgerRow | None

    @property
    def delta(self) -> Decimal | None:
        if self.left is None or self.right is None:
            return None
        return self.left.amount - self.right.amount


@dataclass(frozen=True)
class ReconciliationResult:
    matched: int
    differences: list[Difference]
    total_left: Decimal
    total_right: Decimal


def parse_csv(content: bytes) -> list[LedgerRow]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvValidationError("CSV files must use UTF-8 encoding") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
        raise CsvValidationError("CSV must contain reference, amount, and date columns")
    rows: list[LedgerRow] = []
    for line, raw in enumerate(reader, start=2):
        reference = (raw.get("reference") or "").strip()
        if not reference:
            raise CsvValidationError(f"Row {line}: reference is required")
        try:
            amount = Decimal((raw.get("amount") or "").strip()).quantize(Decimal("0.01"))
            booked_on = date.fromisoformat((raw.get("date") or "").strip())
        except (InvalidOperation, ValueError) as exc:
            raise CsvValidationError(f"Row {line}: invalid amount or ISO date") from exc
        rows.append(LedgerRow(reference, amount, booked_on, (raw.get("description") or "").strip()))
    if not rows:
        raise CsvValidationError("CSV must contain at least one data row")
    return rows


def reconcile(
    left_rows: list[LedgerRow],
    right_rows: list[LedgerRow],
    amount_tolerance: Decimal,
    date_tolerance_days: int,
) -> ReconciliationResult:
    left_by_key: dict[str, list[LedgerRow]] = defaultdict(list)
    right_by_key: dict[str, list[LedgerRow]] = defaultdict(list)
    for row in left_rows:
        left_by_key[row.reference].append(row)
    for row in right_rows:
        right_by_key[row.reference].append(row)

    differences: list[Difference] = []
    matched = 0
    for reference in sorted(set(left_by_key) | set(right_by_key)):
        left_group = left_by_key.get(reference, [])
        right_group = right_by_key.get(reference, [])
        left = left_group[0] if left_group else None
        right = right_group[0] if right_group else None
        if len(left_group) > 1 or len(right_group) > 1:
            differences.append(Difference(reference, "DUPLICATE_KEY", "HIGH", left, right))
        elif left is None:
            differences.append(Difference(reference, "MISSING_LEFT", "HIGH", None, right))
        elif right is None:
            differences.append(Difference(reference, "MISSING_RIGHT", "HIGH", left, None))
        elif abs(left.amount - right.amount) > amount_tolerance:
            delta = abs(left.amount - right.amount)
            severity = "HIGH" if delta >= Decimal("100.00") else "MEDIUM"
            differences.append(Difference(reference, "AMOUNT_MISMATCH", severity, left, right))
        elif abs((left.date - right.date).days) > date_tolerance_days:
            differences.append(Difference(reference, "DATE_MISMATCH", "LOW", left, right))
        else:
            matched += 1

    return ReconciliationResult(
        matched=matched,
        differences=differences,
        total_left=sum((row.amount for row in left_rows), Decimal("0.00")),
        total_right=sum((row.amount for row in right_rows), Decimal("0.00")),
    )

