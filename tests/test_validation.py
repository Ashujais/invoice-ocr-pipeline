"""
Test Suite 1: Valid-field extraction, normalization, and mathematical validation.
"""

from decimal import Decimal
from src.parser import InvoiceParser
from src.validator import InvoiceValidator
from tests.conftest import (
    FIXED_OCR_VALID_101,
    FIXED_OCR_COPY_101,
    FIXED_OCR_VALID_102,
    FIXED_OCR_MATH_MISMATCH,
)


def test_valid_invoice_101_extraction_and_validation():
    """Verify that a standard valid invoice extracts, normalizes, and passes validation."""
    raw = InvoiceParser.parse_raw_text(FIXED_OCR_VALID_101)

    assert raw.raw_invoice_number == "TNM-101"
    assert raw.raw_vendor == "Acme Office Supplies"
    assert raw.raw_date == "2026-10-01"
    assert raw.raw_currency == "INR"
    assert raw.raw_subtotal == "1200.50"
    assert raw.raw_tax == "216.09"
    assert raw.raw_total == "1416.59"

    val_res = InvoiceValidator.validate(raw)
    assert val_res.is_valid is True
    assert val_res.status == "VALID"
    assert len(val_res.errors) == 0
    assert val_res.record is not None

    rec = val_res.record
    assert rec.vendor == "Acme Office Supplies"
    assert rec.vendor_normalized == "acme office supplies"
    assert rec.invoice_number == "TNM-101"
    assert rec.invoice_number_normalized == "TNM-101"
    assert rec.invoice_date == "2026-10-01"
    assert rec.currency == "INR"
    assert rec.subtotal == Decimal("1200.50")
    assert rec.tax == Decimal("216.09")
    assert rec.total == Decimal("1416.59")
    # Verify integer paise conversion
    assert rec.subtotal_paise == 120050
    assert rec.tax_paise == 21609
    assert rec.total_paise == 141659
    assert rec.subtotal_paise + rec.tax_paise == rec.total_paise


def test_valid_invoice_101_copy_formatting_and_date_normalization():
    """Verify comma removal, slash-date parsing, and uppercase vendor normalization."""
    raw = InvoiceParser.parse_raw_text(FIXED_OCR_COPY_101)

    assert raw.raw_subtotal == "1,200.50"
    assert raw.raw_total == "1,416.59"
    assert raw.raw_date == "01/10/2026"

    val_res = InvoiceValidator.validate(raw)
    assert val_res.is_valid is True
    rec = val_res.record
    assert rec.subtotal == Decimal("1200.50")
    assert rec.total == Decimal("1416.59")
    assert rec.invoice_date == "2026-10-01"  # Normalized to ISO format
    assert rec.vendor_normalized == "acme office supplies"


def test_valid_invoice_102():
    """Verify invoice 102 validation."""
    raw = InvoiceParser.parse_raw_text(FIXED_OCR_VALID_102)
    val_res = InvoiceValidator.validate(raw)
    assert val_res.is_valid is True
    assert val_res.record.total == Decimal("1770.00")
    assert val_res.record.total_paise == 177000


def test_mathematical_mismatch_fails_validation():
    """Verify that subtotal + tax != total enters NEEDS_REVIEW with an explicit reason."""
    raw = InvoiceParser.parse_raw_text(FIXED_OCR_MATH_MISMATCH)
    val_res = InvoiceValidator.validate(raw)

    assert val_res.is_valid is False
    assert val_res.status == "NEEDS_REVIEW"
    assert any("Mathematical mismatch" in err for err in val_res.errors)
