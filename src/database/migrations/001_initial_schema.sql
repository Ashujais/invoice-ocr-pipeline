-- ====================================================================
-- SQLite Database Schema for Invoice OCR & Review Pipeline
-- ====================================================================

-- Table 1: Invoices
-- Holds valid, business-level invoice records.
-- Duplicate Key Rationale:
-- A unique constraint on (vendor_normalized, invoice_number_normalized)
-- guarantees that no vendor can insert duplicate invoices, even if case
-- or whitespace differences exist in OCR (e.g. 'ACME OFFICE SUPPLIES' vs
-- 'Acme Office Supplies').
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor TEXT NOT NULL,
    vendor_normalized TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    invoice_number_normalized TEXT NOT NULL,
    invoice_date TEXT NOT NULL,               -- ISO-8601 string 'YYYY-MM-DD'
    currency TEXT NOT NULL,                   -- ISO-4217 3-letter currency code, e.g. 'INR'
    subtotal_decimal TEXT NOT NULL,           -- Decimal string to preserve precision without float drift
    tax_decimal TEXT NOT NULL,                -- Decimal string
    total_decimal TEXT NOT NULL,              -- Decimal string
    subtotal_paise INTEGER NOT NULL,          -- Integer paise (cents) for exact non-float calculations
    tax_paise INTEGER NOT NULL,               -- Integer paise
    total_paise INTEGER NOT NULL,             -- Integer paise
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_vendor_invoice UNIQUE (vendor_normalized, invoice_number_normalized)
);

CREATE INDEX IF NOT EXISTS idx_invoices_vendor_num 
ON invoices (vendor_normalized, invoice_number_normalized);


-- Table 2: Invoice Scans
-- Holds the complete audit log and traceability for every scanned image file.
-- Keeps traceability to all source scans, including duplicates and invalid files.
CREATE TABLE IF NOT EXISTS invoice_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,                  -- SHA-256 hash of the image file
    file_size_bytes INTEGER NOT NULL,
    ocr_engine TEXT NOT NULL,                 -- e.g. 'RapidOCR', 'Tesseract'
    raw_text TEXT NOT NULL,                   -- Full raw OCR output
    status TEXT NOT NULL,                     -- 'VALID', 'DUPLICATE', 'NEEDS_REVIEW', 'ERROR'
    review_reasons TEXT,                      -- JSON list or text describing review reasons / duplicate info
    invoice_id INTEGER,                       -- References invoices.id; NULL if needs_review/error
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_scans_file_hash ON invoice_scans (file_hash);
CREATE INDEX IF NOT EXISTS idx_scans_filename ON invoice_scans (source_filename);
CREATE INDEX IF NOT EXISTS idx_scans_invoice_id ON invoice_scans (invoice_id);
