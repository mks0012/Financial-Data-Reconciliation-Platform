# Architecture

## Data flow

```text
Left CSV + Right CSV
  -> bounded UTF-8 ingestion
  -> schema / decimal / date validation
  -> reference grouping and duplicate detection
  -> amount and date tolerance rules
  -> matched count + typed exceptions
  -> reviewer resolution / reopen
  -> audit evidence + CSV export
```

## Boundaries

- `reconciliation.py` is a deterministic, side-effect-free matching domain.
- The FastAPI layer owns input limits, command validation, persistence, and response contracts.
- SQLAlchemy persists run lineage, typed discrepancies, review state, and audit events.
- The static dashboard consumes only public API endpoints.

## Production path

A deployed version would use PostgreSQL, object storage for encrypted source files, background workers for large runs, tenant isolation, authentication and RBAC, configurable field mappings, maker-checker approval, and metrics/alerts. The matching domain can be parallelized by key partition without changing the exception contract.

