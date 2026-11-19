"""
Database manager for SQLite operations.
Manages connections, schema initialization, duplicate checking, and audit scan logging.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator
from src.models import InvoiceRecord


class DatabaseManager:
    """Manages SQLite database transactions and traceability logs."""

    def __init__(self, db_path: str = "invoices.db"):
        self.db_path = str(db_path)
        self._init_schema()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Create, yield, and reliably close a configured SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Initialize database schema from schema.sql."""
        schema_file = Path(__file__).parent / "schema.sql"
        if schema_file.is_file():
            sql = schema_file.read_text(encoding="utf-8")
        else:
            # Fallback inline schema
            sql = """
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor TEXT NOT NULL,
                vendor_normalized TEXT NOT NULL,
                invoice_number TEXT NOT NULL,
                invoice_number_normalized TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                currency TEXT NOT NULL,
                subtotal_decimal TEXT NOT NULL,
                tax_decimal TEXT NOT NULL,
                total_decimal TEXT NOT NULL,
                subtotal_paise INTEGER NOT NULL,
                tax_paise INTEGER NOT NULL,
                total_paise INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_vendor_invoice UNIQUE (vendor_normalized, invoice_number_normalized)
            );
            CREATE TABLE IF NOT EXISTS invoice_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                ocr_engine TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                status TEXT NOT NULL,
                review_reasons TEXT,
                invoice_id INTEGER,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE SET NULL
            );
            """
        with self._get_connection() as conn:
            conn.executescript(sql)
            conn.commit()

    def find_scan_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Check if an image with the identical file hash has already been recorded in scans."""
        query = "SELECT * FROM invoice_scans WHERE file_hash = ? ORDER BY id DESC LIMIT 1"
        with self._get_connection() as conn:
            row = conn.execute(query, (file_hash,)).fetchone()
            return dict(row) if row else None

    def find_invoice_by_key(
        self, vendor_normalized: str, invoice_number_normalized: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if an invoice with (vendor_normalized, invoice_number_normalized) already exists.
        This represents the duplicate key for business deduplication.
        """
        query = (
            "SELECT * FROM invoices WHERE vendor_normalized = ? "
            "AND invoice_number_normalized = ? LIMIT 1"
        )
        with self._get_connection() as conn:
            row = conn.execute(
                query, (vendor_normalized, invoice_number_normalized)
            ).fetchone()
            return dict(row) if row else None

    def insert_invoice(self, record: InvoiceRecord) -> int:
        """
        Insert a validated invoice into the invoices table.
        
        Returns:
            The primary key integer ID of the created invoice.
            
        Raises:
            sqlite3.IntegrityError: If unique constraint on duplicate key is violated.
        """
        sql = """
        INSERT INTO invoices (
            vendor,
            vendor_normalized,
            invoice_number,
            invoice_number_normalized,
            invoice_date,
            currency,
            subtotal_decimal,
            tax_decimal,
            total_decimal,
            subtotal_paise,
            tax_paise,
            total_paise
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            record.vendor,
            record.vendor_normalized,
            record.invoice_number,
            record.invoice_number_normalized,
            record.invoice_date,
            record.currency,
            str(record.subtotal),
            str(record.tax),
            str(record.total),
            record.subtotal_paise,
            record.tax_paise,
            record.total_paise,
        )
        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.lastrowid

    def record_scan(
        self,
        source_filename: str,
        file_path: str,
        file_hash: str,
        file_size_bytes: int,
        ocr_engine: str,
        raw_text: str,
        status: str,
        review_reasons: Optional[List[str]] = None,
        invoice_id: Optional[int] = None,
    ) -> int:
        """
        Record an entry in the invoice_scans audit log table.
        Maintains complete traceability for all scans (valid, duplicate, or needs_review).
        """
        reasons_str = json.dumps(review_reasons) if review_reasons else None
        sql = """
        INSERT INTO invoice_scans (
            source_filename,
            file_path,
            file_hash,
            file_size_bytes,
            ocr_engine,
            raw_text,
            status,
            review_reasons,
            invoice_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            source_filename,
            file_path,
            file_hash,
            file_size_bytes,
            ocr_engine,
            raw_text,
            status,
            reasons_str,
            invoice_id,
        )
        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.lastrowid

    def get_invoice_by_id(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        """Fetch invoice by primary key ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            return dict(row) if row else None

    def get_all_invoices(self) -> List[Dict[str, Any]]:
        """Fetch all invoices currently stored."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM invoices ORDER BY id ASC").fetchall()
            return [dict(r) for r in rows]

    def get_all_scans(self) -> List[Dict[str, Any]]:
        """Fetch all audit scan records."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM invoice_scans ORDER BY id ASC").fetchall()
            return [dict(r) for r in rows]
