"""
Test Suite 4: Unit tests for parsing and normalization functions.
"""

from decimal import Decimal
from src.parser import InvoiceParser


def test_amount_normalizer_various_formats():
    # Standard decimal
    d, p, err = InvoiceParser.normalize_amount("1500.00", "subtotal")
    assert d == Decimal("1500.00")
    assert p == 150000
    assert err is None

    # Comma separation
    d, p, err = InvoiceParser.normalize_amount("12,345.67", "total")
    assert d == Decimal("12345.67")
    assert p == 1234567
    assert err is None

    # Currency symbol attached
    d, p, err = InvoiceParser.normalize_amount("₹ 250.50", "tax")
    assert d == Decimal("250.50")
    assert p == 25050
    assert err is None

    # Ambiguous characters
    d, p, err = InvoiceParser.normalize_amount("11?0.00", "total")
    assert d is None
    assert "Ambiguous or unparseable" in err

    # Negative amount rejected
    d, p, err = InvoiceParser.normalize_amount("-50.00", "subtotal")
    assert d is None
    assert "Ambiguous or unparseable" in err or "Negative" in err


def test_date_normalizer_various_formats():
    # ISO format
    iso_d, err = InvoiceParser.normalize_date("2026-10-01")
    assert iso_d == "2026-10-01"
    assert err is None

    # Slash day-first
    iso_d, err = InvoiceParser.normalize_date("01/10/2026")
    assert iso_d == "2026-10-01"
    assert err is None

    # Hyphen format
    iso_d, err = InvoiceParser.normalize_date("15-08-2026")
    assert iso_d == "2026-08-15"
    assert err is None

    # Sentinels
    for s in ["[not supplied]", "missing", "N/A", "none"]:
        iso_d, err = InvoiceParser.normalize_date(s)
        assert iso_d is None
        assert "Missing required field" in err


def test_vendor_and_invoice_number_normalizer():
    # Vendor whitespace and lowercase
    disp, norm, err = InvoiceParser.normalize_vendor("  Acme   Office  Supplies  ")
    assert disp == "Acme Office Supplies"
    assert norm == "acme office supplies"
    assert err is None

    # Invoice number uppercase
    disp, norm, err = InvoiceParser.normalize_invoice_number("  tnm-101  ")
    assert disp == "tnm-101"
    assert norm == "TNM-101"
    assert err is None
