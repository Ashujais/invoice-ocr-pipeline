"""
Data models for the invoice processing pipeline.
Uses Decimal and integer paise to guarantee precise financial representation.
"""

from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Optional, List, Dict, Any


@dataclass
class InvoiceRecord:
    """Represents a validated and normalized invoice record ready for persistence."""
    vendor: str
    vendor_normalized: str
    invoice_number: str
    invoice_number_normalized: str
    invoice_date: str          # ISO-8601 YYYY-MM-DD format
    currency: str              # Normalized 3-letter currency code (e.g., 'INR')
    subtotal: Decimal          # Exact decimal
    tax: Decimal               # Exact decimal
    total: Decimal             # Exact decimal
    subtotal_paise: int        # Exact integer paise (cents) avoiding floating-point drift
    tax_paise: int             # Exact integer paise
    total_paise: int           # Exact integer paise

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to a JSON-serializable dictionary."""
        return {
            "vendor": self.vendor,
            "vendor_normalized": self.vendor_normalized,
            "invoice_number": self.invoice_number,
            "invoice_number_normalized": self.invoice_number_normalized,
            "invoice_date": self.invoice_date,
            "currency": self.currency,
            "subtotal": str(self.subtotal),
            "tax": str(self.tax),
            "total": str(self.total),
            "subtotal_paise": self.subtotal_paise,
            "tax_paise": self.tax_paise,
            "total_paise": self.total_paise,
        }


@dataclass
class RawExtraction:
    """Represents unvalidated parsed fields extracted from OCR raw text."""
    raw_text: str
    raw_invoice_number: Optional[str] = None
    raw_vendor: Optional[str] = None
    raw_date: Optional[str] = None
    raw_currency: Optional[str] = None
    raw_subtotal: Optional[str] = None
    raw_tax: Optional[str] = None
    raw_total: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of field validation and mathematical consistency checks."""
    is_valid: bool
    status: str                         # 'VALID', 'NEEDS_REVIEW'
    errors: List[str] = field(default_factory=list)
    record: Optional[InvoiceRecord] = None
    raw_extraction: Optional[RawExtraction] = None


@dataclass
class ProcessingResult:
    """Outcome of processing an individual image file through OCR, validation, and storage."""
    source_filename: str
    file_path: str
    file_hash: str
    status: str                         # 'VALID', 'DUPLICATE', 'NEEDS_REVIEW', 'ERROR'
    review_reasons: List[str] = field(default_factory=list)
    invoice_record: Optional[InvoiceRecord] = None
    raw_extraction: Optional[RawExtraction] = None
    invoice_id: Optional[int] = None    # Database ID in invoices table
    scan_id: Optional[int] = None       # Database ID in invoice_scans table
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result for reporting."""
        record_dict = self.invoice_record.to_dict() if self.invoice_record else None
        raw_dict = {
            "invoice_number": self.raw_extraction.raw_invoice_number if self.raw_extraction else None,
            "vendor": self.raw_extraction.raw_vendor if self.raw_extraction else None,
            "invoice_date": self.raw_extraction.raw_date if self.raw_extraction else None,
            "currency": self.raw_extraction.raw_currency if self.raw_extraction else None,
            "subtotal": self.raw_extraction.raw_subtotal if self.raw_extraction else None,
            "tax": self.raw_extraction.raw_tax if self.raw_extraction else None,
            "total": self.raw_extraction.raw_total if self.raw_extraction else None,
        } if self.raw_extraction else None

        return {
            "source_filename": self.source_filename,
            "file_hash": self.file_hash,
            "status": self.status,
            "invoice_id": self.invoice_id,
            "scan_id": self.scan_id,
            "review_reasons": self.review_reasons,
            "invoice_record": record_dict,
            "extracted_raw_fields": raw_dict,
            "raw_text_preview": (self.raw_text[:200] + "...") if len(self.raw_text) > 200 else self.raw_text,
        }
