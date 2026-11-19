"""
Test Suite 3: Incomplete and ambiguous invoice input handling.
Verifies missing fields, OCR artifacts, and review queue mechanics.
"""

from src.parser import InvoiceParser
from src.validator import InvoiceValidator
from src.pipeline import InvoicePipeline
from tests.conftest import FIXED_OCR_AMBIGUOUS_103
from tests.test_duplicate import MockOCREngine


def test_ambiguous_invoice_103_reasons():
    """
    invoice-103 has a missing date ('[not supplied]') and ambiguous total ('11?0.00').
    Verify it enters NEEDS_REVIEW with both reasons explicitly documented.
    """
    raw = InvoiceParser.parse_raw_text(FIXED_OCR_AMBIGUOUS_103)

    assert raw.raw_invoice_number == "TNM-103"
    assert raw.raw_vendor == "Gamma Paper Co"
    assert raw.raw_date == "[not supplied]"
    assert raw.raw_total == "11?0.00"

    val_res = InvoiceValidator.validate(raw)

    assert val_res.is_valid is False
    assert val_res.status == "NEEDS_REVIEW"
    assert val_res.record is None

    # Must contain both distinct errors
    assert any("invoice_date" in err for err in val_res.errors)
    assert any("11?0.00" in err for err in val_res.errors)


def test_missing_vendor_and_invoice_number():
    """Verify that completely missing vendor or invoice number fails validation."""
    ocr_missing = """
    Date: 2026-10-01
    Currency: INR
    Subtotal: 100.00
    Tax: 18.00
    Total: 118.00
    """
    raw = InvoiceParser.parse_raw_text(ocr_missing)
    val_res = InvoiceValidator.validate(raw)

    assert val_res.is_valid is False
    assert any("vendor" in err for err in val_res.errors)
    assert any("invoice_number" in err for err in val_res.errors)


def test_invalid_invoice_not_stored_in_invoices_table(temp_db, tmp_path):
    """
    Incomplete or ambiguous records must NOT insert a row into invoices table,
    but MUST be recorded in invoice_scans for human review traceability.
    """
    img = tmp_path / "invoice-103-review.png"
    img.write_bytes(b"dummy image 103 content")

    mock_engine = MockOCREngine({
        "invoice-103-review.png": FIXED_OCR_AMBIGUOUS_103,
    })

    pipeline = InvoicePipeline(
        ocr_engine=mock_engine,
        db_manager=temp_db,
        raw_ocr_dir=tmp_path / "raw_ocr",
    )

    results = pipeline.process_directory(tmp_path)
    assert len(results) == 1
    res = results[0]

    assert res.status == "NEEDS_REVIEW"
    assert res.invoice_id is None
    assert res.scan_id is not None
    assert len(res.review_reasons) >= 2

    # Verify database state
    all_invoices = temp_db.get_all_invoices()
    assert len(all_invoices) == 0  # Not stored in invoices table

    all_scans = temp_db.get_all_scans()
    assert len(all_scans) == 1
    assert all_scans[0]["status"] == "NEEDS_REVIEW"
    assert all_scans[0]["invoice_id"] is None
    assert "invoice_date" in all_scans[0]["review_reasons"]
