"""
Test Suite 2: Duplicate detection, repeated import idempotency, and audit traceability.
"""

from src.parser import InvoiceParser
from src.validator import InvoiceValidator
from src.pipeline import InvoicePipeline
from src.ocr.base import BaseOCREngine
from tests.conftest import (
    FIXED_OCR_VALID_101,
    FIXED_OCR_COPY_101,
    FIXED_OCR_VALID_102,
)


class MockOCREngine(BaseOCREngine):
    """Mock OCR engine returning predetermined text keyed by filename."""

    def __init__(self, mapping):
        self.mapping = mapping

    @property
    def name(self) -> str:
        return "MockOCR"

    def extract_text(self, image_path) -> str:
        from pathlib import Path
        name = Path(image_path).name
        return self.mapping.get(name, "")


def test_duplicate_scan_links_to_existing_invoice(temp_db):
    """
    Importing an invoice, followed by another scan of the same invoice (even with
    different casing/formatting), must link the second scan as DUPLICATE and NOT
    insert a second invoice record.
    """
    # 1. Parse and insert original scan (invoice-101.png)
    val1 = InvoiceValidator.validate(InvoiceParser.parse_raw_text(FIXED_OCR_VALID_101))
    assert val1.is_valid is True

    # Check duplicate key before insert
    existing = temp_db.find_invoice_by_key(
        val1.record.vendor_normalized, val1.record.invoice_number_normalized
    )
    assert existing is None

    inv_id1 = temp_db.insert_invoice(val1.record)
    scan_id1 = temp_db.record_scan(
        source_filename="invoice-101.png",
        file_path="/mock/invoice-101.png",
        file_hash="hash_101",
        file_size_bytes=1000,
        ocr_engine="MockOCR",
        raw_text=FIXED_OCR_VALID_101,
        status="VALID",
        invoice_id=inv_id1,
    )

    # 2. Parse copy scan (invoice-101-copy.png with vendor 'ACME OFFICE SUPPLIES')
    val2 = InvoiceValidator.validate(InvoiceParser.parse_raw_text(FIXED_OCR_COPY_101))
    assert val2.is_valid is True

    # Check duplicate key
    existing_inv = temp_db.find_invoice_by_key(
        val2.record.vendor_normalized, val2.record.invoice_number_normalized
    )
    assert existing_inv is not None
    assert existing_inv["id"] == inv_id1

    # Record scan as duplicate linked to original invoice
    scan_id2 = temp_db.record_scan(
        source_filename="invoice-101-copy.png",
        file_path="/mock/invoice-101-copy.png",
        file_hash="hash_copy",
        file_size_bytes=1050,
        ocr_engine="MockOCR",
        raw_text=FIXED_OCR_COPY_101,
        status="DUPLICATE",
        review_reasons=[f"Duplicate scan of existing invoice ID {inv_id1}"],
        invoice_id=inv_id1,
    )

    # 3. Assert invariants:
    # Exactly 1 invoice in invoices table
    all_invoices = temp_db.get_all_invoices()
    assert len(all_invoices) == 1
    assert all_invoices[0]["id"] == inv_id1
    assert all_invoices[0]["invoice_number"] == "TNM-101"

    # Exactly 2 scans in invoice_scans table, both pointing to invoice_id1
    all_scans = temp_db.get_all_scans()
    assert len(all_scans) == 2
    assert all_scans[0]["source_filename"] == "invoice-101.png"
    assert all_scans[0]["status"] == "VALID"
    assert all_scans[0]["invoice_id"] == inv_id1

    assert all_scans[1]["source_filename"] == "invoice-101-copy.png"
    assert all_scans[1]["status"] == "DUPLICATE"
    assert all_scans[1]["invoice_id"] == inv_id1


def test_repeated_run_idempotency(temp_db, tmp_path):
    """
    Running the pipeline twice on the same directory must not insert duplicate invoice records.
    """
    # Create fake image files
    img1 = tmp_path / "invoice-101.png"
    img1.write_bytes(b"dummy image 101 content")

    img2 = tmp_path / "invoice-102.png"
    img2.write_bytes(b"dummy image 102 content")

    mock_engine = MockOCREngine({
        "invoice-101.png": FIXED_OCR_VALID_101,
        "invoice-102.png": FIXED_OCR_VALID_102,
    })

    pipeline = InvoicePipeline(
        ocr_engine=mock_engine,
        db_manager=temp_db,
        raw_ocr_dir=tmp_path / "raw_ocr",
    )

    # First run
    results_run1 = pipeline.process_directory(tmp_path)
    assert len(results_run1) == 2
    assert all(r.status == "VALID" for r in results_run1)

    invoices_run1 = temp_db.get_all_invoices()
    scans_run1 = temp_db.get_all_scans()
    assert len(invoices_run1) == 2
    assert len(scans_run1) == 2

    # Second run on the same directory
    results_run2 = pipeline.process_directory(tmp_path)
    assert len(results_run2) == 2

    invoices_run2 = temp_db.get_all_invoices()
    scans_run2 = temp_db.get_all_scans()

    # Zero duplicate invoices or duplicate scans inserted!
    assert len(invoices_run2) == 2
    assert len(scans_run2) == 2
