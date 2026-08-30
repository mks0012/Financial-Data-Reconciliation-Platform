# Financial Data Reconciliation Platform

An automated data reconciliation and exception operations engine built with Python, FastAPI, and SQL. The system ingests high-volume financial datasets, performs multi-tier tolerance matching, and classifies exceptions for Root Cause Analysis (RCA) and compliance auditing.

## Key Features
- **Automated Ingestion Pipeline:** Processes transactional feeds and statements across varying data schemas.
- **Configurable Tolerance Matching:** Multi-level matching rules including absolute and percentage-based variance thresholds.
- **Exception & RCA Routing:** Automated triage for discrepancies, flagging fee mismatches, timing differences, and missing records.
- **Audit-Ready Reporting:** Structured exports formatted for regulatory compliance and operational review.

## Tech Stack
- **Backend:** Python 3.12, FastAPI, SQLAlchemy, Pydantic
- **Database:** PostgreSQL / SQLite
- **Containerization:** Docker, Docker Compose

## Quick Start

1. Clone and setup environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt