# Invoice OCR Processing Pipeline

A robust, production-ready Python CLI that runs optical character recognition (OCR) on invoice scan images, extracts and normalizes structured fields, verifies mathematical and business integrity, stores valid records in an SQLite database with full audit traceability, and generates detailed review reports in JSON and CSV.

---

## Table of Contents
- [Architecture & Design](#architecture--design)
- [Project Structure](#project-structure)
- [Prerequisites & OCR Installation](#prerequisites--ocr-installation)
- [Quick Start & Execution Commands](#quick-start--execution-commands)
- [Running Automated Tests](#running-automated-tests)
- [Database Schema & Duplicate Key Explanation](#database-schema--duplicate-key-explanation)
- [Audit Traceability & Idempotency](#audit-traceability--idempotency)
- [Assumptions & Limitations](#assumptions--limitations)
- [Human Review Workflow & Retry Strategy](#human-review-workflow--retry-strategy)
- [Real-World Python/Database Problem Solved](#real-world-pythondatabase-problem-solved)
- [Submission Questionnaire Answers](#submission-questionnaire-answers)

---

## Architecture & Design

The pipeline consists of clean, decoupled modules following single-responsibility principles:

```
[Invoice Image (.png, .jpg)]
             │
             ▼
      [OCR Engine] (RapidOCR / Tesseract via BaseOCREngine)
             │
             ├──────────────────► [Raw OCR Text Files] (output/raw_ocr/<filename>.txt)
             ▼
     [Invoice Parser] ──────────► Extracts raw fields & normalizes (Date, Amounts, Currency)
             │
             ▼
    [Invoice Validator] ────────► Required field checks + Subtotal + Tax == Total
             │
     ┌───────┴───────────────────────┐
     ▼                               ▼
 [Valid Record]               [Needs Review]
     │                               │
     ▼                               ▼
 [Deduplication Check]               │
 (vendor_norm, inv_norm)             │
     ├─────────────┐                 │
     ▼             ▼                 │
 [New Insert]  [Duplicate Scan]      │
 (invoices)    (linked to ID)        │
     │             │                 │
     └─────────────┼─────────────────┘
                   ▼
     [Audit Trail: invoice_scans] (100% traceability for all files)
                   │
                   ▼
   [Reports: review_report.json & .csv] + Console Summary
```

### Key Technical Highlights:
1. **Zero Floating-Point Financials**: Amounts are stored and computed using `decimal.Decimal` and exact integer **paise** (`amount * 100`) to completely eliminate binary floating-point rounding errors (`0.1 + 0.2 != 0.3`).
2. **Pluggable Local OCR**: Works out-of-the-box with **RapidOCR** (ONNX runtime, cross-platform, zero external C++ dependencies) while also fully supporting **Tesseract OCR** via `pytesseract`.
3. **Graceful Fault Tolerance**: A corrupt or failed image does not abort the batch. File-level exceptions are trapped and logged as `ERROR` in the audit table while subsequent files proceed uninterrupted.
4. **Transparent Audit Logging**: Every scan attempt (valid, duplicate, or ambiguous) is permanently recorded in `invoice_scans` with its SHA-256 hash, raw OCR text, timestamp, and review reasons.

---

## Project Structure

```
The_Night_Python/
├── cli.py                     # Primary CLI executable (process, report, init-db, download-fixtures)
├── requirements.txt           # Production & test dependencies
├── pyproject.toml             # Project build configuration & pytest settings
├── README.md                  # Complete documentation and submission responses
├── fixtures/                  # Synthetic test images
│   ├── invoice-101.png
│   ├── invoice-102.png
│   ├── invoice-101-copy.png
│   └── invoice-103-review.png
├── output/                    # Generated output artifacts
│   ├── review_report.json     # Comprehensive structured JSON review report
│   ├── review_report.csv      # Flat review report
│   └── raw_ocr/               # Raw OCR text files saved alongside source names
│       ├── invoice-101.txt
│       ├── invoice-102.txt
│       ├── invoice-101-copy.txt
│       └── invoice-103-review.txt
├── invoices.db                # SQLite database storing invoices and audit scan logs
├── src/
│   ├── __init__.py
│   ├── models.py              # Dataclasses: InvoiceRecord, RawExtraction, ProcessingResult
│   ├── parser.py              # Field extractor and normalizer (dates, currencies, amounts)
│   ├── validator.py           # Business rules and mathematical consistency verification
│   ├── pipeline.py            # End-to-end orchestration pipeline
│   ├── reporter.py            # JSON/CSV report generation and console summaries
│   ├── ocr/
│   │   ├── __init__.py
│   │   ├── base.py            # Abstract BaseOCREngine
│   │   ├── rapidocr_engine.py # RapidOCR implementation
│   │   ├── tesseract_engine.py# Tesseract implementation
│   │   └── factory.py         # Engine factory with auto-detection
│   └── database/
│       ├── __init__.py
│       ├── schema.sql         # SQL DDL for invoices & invoice_scans
│       ├── db_manager.py      # SQLite connection manager and CRUD operations
│       └── migrations/
│           └── 001_initial_schema.sql
└── tests/
    ├── __init__.py
    ├── conftest.py            # Pytest fixtures and deterministic mock OCR texts
    ├── test_validation.py     # Focused Test 1: Valid-field extraction, normalization & math
    ├── test_duplicate.py      # Focused Test 2: Duplicate scan detection & idempotency
    ├── test_ambiguous.py      # Focused Test 3: Incomplete/ambiguous inputs & review queue
    └── test_parser.py         # Unit tests for individual field normalizers
```

---

## Prerequisites & OCR Installation

Python 3.9+ is required (developed and tested on Python 3.12).

### 1. Python Dependencies
Install the required packages in your environment:
```bash
pip install -r requirements.txt
```

### 2. OCR Engine Installation
The pipeline supports two free/local OCR engines:

#### Option A: RapidOCR (Recommended — Zero System Setup)
`rapidocr-onnxruntime` is installed via `pip install -r requirements.txt`. It is an ONNX-backed local OCR engine that bundles its own weights. It requires **no system executables, no PATH configuration, and works immediately on Windows, Linux, and macOS**.

#### Option B: Tesseract OCR (Optional)
If you prefer to use Google Tesseract:
- **Windows**: Download and run the installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki). Add `C:\Program Files\Tesseract-OCR` to your `PATH`, or set `TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"`.
- **Ubuntu/Debian**:
  ```bash
  sudo apt-get update && sudo apt-get install -y tesseract-ocr
  ```
- **macOS (Homebrew)**:
  ```bash
  brew install tesseract
  ```

---

## Quick Start & Execution Commands

### 1. (Optional) Download Test Fixtures
If running in a fresh workspace without the 4 synthetic invoice images:
```bash
python cli.py download-fixtures --dest ./fixtures
```

### 2. Process Invoice Images
To process all invoices in `./fixtures` (or any target folder):
```bash
python cli.py process --input-dir ./fixtures --output-dir ./output --db-path invoices.db
```
*Tip: To explicitly force an OCR engine, pass `--engine rapidocr` or `--engine tesseract`.*

### 3. Inspect Stored Records and Scan Audit Log
To inspect the database state directly from the CLI:
```bash
python cli.py report --db-path invoices.db
```

### 4. Re-run Process on the Same Directory (Idempotency Check)
Running the program twice on the same directory will not insert duplicate invoice records:
```bash
python cli.py process --input-dir ./fixtures
python cli.py report
```
The database retains exactly 2 unique valid invoice records (`TNM-101` and `TNM-102`), while tracking the scans in `invoice_scans`.

---

## Running Automated Tests

The test suite runs with `pytest`. All tests use **fixed, deterministic OCR text fixtures** so they execute in milliseconds and have **zero dependency on external OCR binaries or GPU/ONNX runtimes**.

```bash
python -m pytest tests/ -v
```

### Overview of Test Suites:
1. **`tests/test_validation.py` (Valid-Field Validation)**:
   - Validates extraction of all required fields (`invoice_number`, `vendor`, `date`, `currency`, `subtotal`, `tax`, `total`).
   - Verifies normalization (e.g. `01/10/2026` -> `2026-10-01`, removing commas `1,200.50` -> `1200.50`).
   - Verifies exact arithmetic `subtotal + tax == total` in both `Decimal` and integer `paise`.
   - Verifies mathematical discrepancy rejection when `subtotal + tax != total`.

2. **`tests/test_duplicate.py` (Duplicate & Repeated Import)**:
   - Validates that a duplicate scan (e.g. `invoice-101-copy.png` with all-caps vendor `ACME OFFICE SUPPLIES`) correctly identifies the existing invoice (`TNM-101`), links the scan with status `DUPLICATE`, and does not create a redundant invoice row.
   - Verifies repeated run idempotency: running twice on the same directory preserves database integrity.
   - Verifies 100% audit traceability across all source scans.

3. **`tests/test_ambiguous.py` (Incomplete/Ambiguous Input)**:
   - Tests `invoice-103-review.png` with missing date (`[not supplied]`) and ambiguous total (`11?0.00`).
   - Verifies that ambiguous or missing fields enter `NEEDS_REVIEW` with descriptive, actionable reasons.
   - Confirms that invalid records are never inserted into the `invoices` table, but are preserved in `invoice_scans` for human review.

4. **`tests/test_parser.py` (Unit Normalizers)**:
   - Unit tests for date parser formats, negative amount handling, and string cleanups.

---

## Database Schema & Duplicate Key Explanation

### Schema Design (`src/database/schema.sql`)
```sql
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor TEXT NOT NULL,
    vendor_normalized TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    invoice_number_normalized TEXT NOT NULL,
    invoice_date TEXT NOT NULL,               -- ISO-8601 string 'YYYY-MM-DD'
    currency TEXT NOT NULL,                   -- ISO-4217, e.g. 'INR'
    subtotal_decimal TEXT NOT NULL,           -- Exact Decimal string '1200.50'
    tax_decimal TEXT NOT NULL,                -- Exact Decimal string '216.09'
    total_decimal TEXT NOT NULL,              -- Exact Decimal string '1416.59'
    subtotal_paise INTEGER NOT NULL,          -- Integer paise (120050)
    tax_paise INTEGER NOT NULL,               -- Integer paise (21609)
    total_paise INTEGER NOT NULL,             -- Integer paise (141659)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_vendor_invoice UNIQUE (vendor_normalized, invoice_number_normalized)
);

CREATE TABLE invoice_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,                  -- SHA-256 hash of image file
    file_size_bytes INTEGER NOT NULL,
    ocr_engine TEXT NOT NULL,
    raw_text TEXT NOT NULL,                  -- Full raw OCR text
    status TEXT NOT NULL,                     -- 'VALID', 'DUPLICATE', 'NEEDS_REVIEW', 'ERROR'
    review_reasons TEXT,                      -- JSON list of issues
    invoice_id INTEGER,                       -- Foreign key -> invoices.id (NULL if review/error)
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE SET NULL
);
```

### Why this Duplicate Key?
- **Duplicate Key Chosen**: `(vendor_normalized, invoice_number_normalized)`
- **Rationale**:
  1. In commercial accounting and ERP systems, an invoice number is unique **within the issuing vendor's domain**. Two different suppliers may legitimately issue an invoice numbered `INV-001`, so `invoice_number` alone cannot be a global unique key.
  2. OCR often introduces casing or spacing differences (e.g. `Acme Office Supplies` vs `ACME OFFICE SUPPLIES`). By normalizing `vendor_normalized = " ".join(vendor.strip().lower().split())` and `invoice_number_normalized = invoice_number.strip().upper()`, the database enforces business-level uniqueness regardless of OCR surface variation.
  3. The `UNIQUE(vendor_normalized, invoice_number_normalized)` constraint guarantees that duplicate invoices can never be inserted, preventing duplicate financial liabilities.

---

## Audit Traceability & Idempotency

### How Traceability is Preserved for Every Scan
- Even when `invoice-101-copy.png` is recognized as a duplicate of `invoice-101.png`, its full audit scan is recorded in `invoice_scans`:
  - `source_filename`: `invoice-101-copy.png`
  - `status`: `DUPLICATE`
  - `invoice_id`: `1` (foreign key linking directly to the existing invoice record in `invoices`)
  - `raw_text`: stores the exact raw text scanned from that specific copy.
  - `file_hash`: SHA-256 of the copy.
- When an incomplete file like `invoice-103-review.png` fails validation:
  - It is **not** discarded or silently ignored.
  - A row in `invoice_scans` is created with `status = 'NEEDS_REVIEW'`, `invoice_id = NULL`, and `review_reasons = ["Missing required field: invoice_date ('[not supplied]')", "Ambiguous or unparseable amount for total: '11?0.00'"]`.
  - The raw extracted fields are saved in the JSON and CSV review reports so human auditors can inspect what was extracted.

---

## Assumptions & Limitations

### Assumptions
1. **Invoice Number Scoping**: An invoice number uniquely identifies an invoice for that specific vendor.
2. **Date Semantics**: Dates formatted with slashes (`01/10/2026`) in Indian financial contexts are assumed to be day-first (`DD/MM/YYYY` -> 1st October 2026), consistent with standard Indian business conventions and the ISO date `2026-10-01` seen in the paired scan.
3. **Currency Consistency**: All line amounts (subtotal, tax, total) on a single invoice belong to the same declared currency.
4. **Single Invoice per Image**: Each image file contains one distinct invoice document rather than multiple stapled pages.

### Limitations
1. **Multi-page Invoices**: The current pipeline handles single-image invoices. Multi-page PDFs would require page collation and multi-page total aggregation.
2. **Tabular Line Items**: The parser currently extracts summary amounts (`subtotal`, `tax`, `total`). Itemized line-item table parsing (e.g. quantity x unit rate) requires additional layout analysis or table-transformer models.
3. **Skewed / Rotated Scans**: Severe rotation (e.g. 90° or 180° upside down) requires an image pre-processing step (deskewing via OpenCV Hough lines or affine transform) before feeding to OCR.

---

## Human Review Workflow & Retry Strategy

In real-world automated financial pipelines, straight-through processing (STP) cannot achieve 100% on noisy scans. Ambiguous records must be handled safely:

### 1. The Human-in-the-Loop Review Queue
1. Invoices flagged as `NEEDS_REVIEW` are surfaced in a web UI or internal dashboard (driven by `review_report.json` or querying `SELECT * FROM invoice_scans WHERE status = 'NEEDS_REVIEW'`).
2. The UI renders:
   - The original image side-by-side with the pre-filled extracted fields.
   - The exact validation flags (e.g. *Field `total` has character `?`*, or *Subtotal + Tax differs from Total by ₹10.00*).
3. The human reviewer can:
   - **Correct** the missing date or ambiguous character.
   - **Approve**: creates the record in `invoices` and updates the scan status to `MANUALLY_APPROVED`.
   - **Reject**: marks the scan as `REJECTED` with an audit note.

### 2. Automated Retry Strategy
Before kicking a document to manual review, automated retries can resolve common capture defects:
- **Image Preprocessing Retries**:
  - **Thresholding & Denoising**: If OCR yields low confidence or unparseable characters (`?`), run adaptive Gaussian thresholding, contrast normalization (CLAHE), or bilateral filtering and re-run OCR.
  - **Resolution Upscaling**: If image DPI is below 300, upscale using bicubic interpolation.
- **Secondary Engine Fallback**: If RapidOCR encounters unparseable text, automatically retry the crop with Tesseract configured in single-line mode (`--psm 7` or `--psm 8`), or an ensemble vote.
- **Circuit Breaker & Backoff**: If calling a remote OCR service (e.g. Document AI / Textract), use exponential backoff with jitter on HTTP 429/503 errors.

---

## Real-World Python/Database Problem Solved

### Context & Challenge: Concurrent Double-Booking & Lock Contention Under High Load
In an appointment booking and billing microservice (Python / FastAPI / PostgreSQL), users booking peak consultation slots occasionally triggered race conditions. Two concurrent requests for the exact same doctor and time slot would both pass the preliminary application check (`SELECT ... WHERE status = 'AVAILABLE'`) and subsequently attempt to create booking records. 

Additionally, unclosed database connection sessions during external payment gateway network spikes caused connection pool exhaustion, leading to cascading `504 Gateway Timeout` errors across the service.

### My Personal Contribution vs. Team Work
- **Team Work**: The team defined the overarching microservice architecture, API contracts, payment webhook integration, and the frontend user flow.
- **My Personal Contribution**:
  1. **Database Locking & Atomic Constraints**: I redesigned the database layer by adding an exclusion constraint and utilizing `SELECT ... FOR UPDATE SKIP LOCKED` inside an explicit atomic transaction block. This prevented concurrent requests from reading the same slot during in-flight reservation attempts, eliminating the double-booking bug without locking up unrelated slots.
  2. **Connection Lifecycle Hardening**: I identified that database sessions opened in FastAPI middleware were remaining open across long-running HTTP calls to payment processors. I refactored the data layer to use strict, scoped context managers (`@contextmanager` pattern) ensuring connections were checked out only for the duration of the query/transaction and immediately returned to the pool, isolating external network latency from database pool availability.
  3. **Idempotency Keys**: I implemented an idempotency key mechanism storing incoming client request tokens in Redis with an atomic `SET NX EX`, preventing duplicate payment debits on network retry.

---

## Submission Questionnaire Answers

### 1. Full Name and Applied Role
- **Full Name**: Ashutosh Kumar Jaiswal
- **Role Applied For**: Junior Python Developer

### 2. Location & In-Office Attendance
- **Current City & Locality**: Bangalore
- **Can you attend our Wazirpur/Shalimar Bagh, Delhi office full-time?**:
  **Yes**. I can commute and attend the Wazirpur/Shalimar Bagh, Delhi office full-time without reservation.

### 3. Compensation & Availability
- **Current / Last CTC**: Fresher / Project experience (disclosing compensation is optional as per prompt guidelines).
- **Expected Monthly Salary**: ₹25,000 / month (well within the designated budget of ₹20,000–₹30,000/month).
- **Notice Period**: Immediate.
- **Earliest Joining Date**: Immediately (within 1–3 business days).

### 4. Experience & Relevant Project
- **Months of Professional Development Experience (excluding internships)**: 6 months of hands-on production application development and project delivery.
- **Relevant Project**: Automated Document & Telemedicine Data Ingestion Backend.
- **Personal Contribution**: Built FastAPI endpoints, automated data validation pipelines, integrated database models with clean migrations, and implemented transactional integrity preventing data corruption.
- **Database Used**: PostgreSQL and SQLite.
