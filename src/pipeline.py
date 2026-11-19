"""
Core pipeline orchestrator for invoice processing.
Coordinates OCR, text storage, field parsing, business validation, and database persistence.
"""

import hashlib
import logging
from pathlib import Path
from typing import List, Union, Optional

from src.models import ProcessingResult, ValidationResult, InvoiceRecord
from src.ocr.base import BaseOCREngine
from src.parser import InvoiceParser
from src.validator import InvoiceValidator
from src.database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class InvoicePipeline:
    """End-to-end processing pipeline for invoice documents."""

    def __init__(
        self,
        ocr_engine: BaseOCREngine,
        db_manager: DatabaseManager,
        raw_ocr_dir: Optional[Union[str, Path]] = None,
    ):
        self.ocr_engine = ocr_engine
        self.db = db_manager
        self.raw_ocr_dir = Path(raw_ocr_dir) if raw_ocr_dir else None
        if self.raw_ocr_dir:
            self.raw_ocr_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute SHA-256 hash of a file for content verification and duplicate detection."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def process_file(self, file_path: Union[str, Path]) -> ProcessingResult:
        """
        Process a single image file through OCR, parsing, validation, and database storage.
        Catches file-specific errors so one failure does not halt batch processing.
        """
        path = Path(file_path).resolve()
        filename = path.name

        try:
            if not path.is_file():
                return ProcessingResult(
                    source_filename=filename,
                    file_path=str(path),
                    file_hash="",
                    status="ERROR",
                    review_reasons=[f"File not found: {path}"],
                )

            # 1. File metadata & hash
            file_hash = self.compute_sha256(path)
            file_size = path.stat().st_size

            # Check if this exact file scan already exists in database (idempotency check)
            existing_scan = self.db.find_scan_by_hash(file_hash)
            if existing_scan:
                logger.info(f"File {filename} (hash {file_hash[:8]}...) was already scanned.")
                reasons = []
                if existing_scan["review_reasons"]:
                    import json
                    try:
                        reasons = json.loads(existing_scan["review_reasons"])
                    except Exception:
                        reasons = [existing_scan["review_reasons"]]

                inv_rec = None
                if existing_scan["invoice_id"]:
                    inv_row = self.db.get_invoice_by_id(existing_scan["invoice_id"])
                    if inv_row:
                        from decimal import Decimal
                        inv_rec = InvoiceRecord(
                            vendor=inv_row["vendor"],
                            vendor_normalized=inv_row["vendor_normalized"],
                            invoice_number=inv_row["invoice_number"],
                            invoice_number_normalized=inv_row["invoice_number_normalized"],
                            invoice_date=inv_row["invoice_date"],
                            currency=inv_row["currency"],
                            subtotal=Decimal(inv_row["subtotal_decimal"]),
                            tax=Decimal(inv_row["tax_decimal"]),
                            total=Decimal(inv_row["total_decimal"]),
                            subtotal_paise=inv_row["subtotal_paise"],
                            tax_paise=inv_row["tax_paise"],
                            total_paise=inv_row["total_paise"],
                        )

                raw_ext = None
                if existing_scan["raw_text"]:
                    raw_ext = InvoiceParser.parse_raw_text(existing_scan["raw_text"])

                return ProcessingResult(
                    source_filename=filename,
                    file_path=str(path),
                    file_hash=file_hash,
                    status=existing_scan["status"],
                    review_reasons=reasons,
                    invoice_record=inv_rec,
                    raw_extraction=raw_ext,
                    invoice_id=existing_scan["invoice_id"],
                    scan_id=existing_scan["id"],
                    raw_text=existing_scan["raw_text"],
                )

            # 2. OCR Execution
            logger.info(f"Running {self.ocr_engine.name} on {filename}...")
            raw_text = self.ocr_engine.extract_text(path)

            # 3. Save raw OCR text alongside source filename
            if self.raw_ocr_dir:
                raw_text_file = self.raw_ocr_dir / f"{path.stem}.txt"
                raw_text_file.write_text(raw_text, encoding="utf-8")

            # 4. Parse extracted fields
            raw_extraction = InvoiceParser.parse_raw_text(raw_text)

            # 5. Validate business rules and mathematics
            validation: ValidationResult = InvoiceValidator.validate(raw_extraction)

            # 6. Database Storage & Deduplication
            if validation.is_valid and validation.record:
                rec = validation.record
                # Check duplicate key: (vendor_normalized, invoice_number_normalized)
                existing_invoice = self.db.find_invoice_by_key(
                    rec.vendor_normalized, rec.invoice_number_normalized
                )

                if existing_invoice:
                    # Duplicate invoice scan detected!
                    inv_id = existing_invoice["id"]
                    status = "DUPLICATE"
                    reasons = [
                        f"Duplicate scan of existing invoice ID {inv_id} "
                        f"(Vendor: '{existing_invoice['vendor']}', Invoice: '{existing_invoice['invoice_number']}')"
                    ]
                    # Link scan to the original invoice, keeping 100% traceability without inserting duplicate
                    scan_id = self.db.record_scan(
                        source_filename=filename,
                        file_path=str(path),
                        file_hash=file_hash,
                        file_size_bytes=file_size,
                        ocr_engine=self.ocr_engine.name,
                        raw_text=raw_text,
                        status=status,
                        review_reasons=reasons,
                        invoice_id=inv_id,
                    )
                    return ProcessingResult(
                        source_filename=filename,
                        file_path=str(path),
                        file_hash=file_hash,
                        status=status,
                        review_reasons=reasons,
                        invoice_record=rec,
                        raw_extraction=raw_extraction,
                        invoice_id=inv_id,
                        scan_id=scan_id,
                        raw_text=raw_text,
                    )
                else:
                    # New distinct valid invoice
                    inv_id = self.db.insert_invoice(rec)
                    status = "VALID"
                    scan_id = self.db.record_scan(
                        source_filename=filename,
                        file_path=str(path),
                        file_hash=file_hash,
                        file_size_bytes=file_size,
                        ocr_engine=self.ocr_engine.name,
                        raw_text=raw_text,
                        status=status,
                        review_reasons=[],
                        invoice_id=inv_id,
                    )
                    return ProcessingResult(
                        source_filename=filename,
                        file_path=str(path),
                        file_hash=file_hash,
                        status=status,
                        review_reasons=[],
                        invoice_record=rec,
                        raw_extraction=raw_extraction,
                        invoice_id=inv_id,
                        scan_id=scan_id,
                        raw_text=raw_text,
                    )
            else:
                # Validation failed -> enters NEEDS_REVIEW
                status = "NEEDS_REVIEW"
                reasons = validation.errors
                scan_id = self.db.record_scan(
                    source_filename=filename,
                    file_path=str(path),
                    file_hash=file_hash,
                    file_size_bytes=file_size,
                    ocr_engine=self.ocr_engine.name,
                    raw_text=raw_text,
                    status=status,
                    review_reasons=reasons,
                    invoice_id=None,
                )
                return ProcessingResult(
                    source_filename=filename,
                    file_path=str(path),
                    file_hash=file_hash,
                    status=status,
                    review_reasons=reasons,
                    invoice_record=None,
                    raw_extraction=raw_extraction,
                    invoice_id=None,
                    scan_id=scan_id,
                    raw_text=raw_text,
                )

        except Exception as exc:
            logger.exception(f"Unexpected error processing {filename}: {exc}")
            # Ensure scan failure is logged if possible
            try:
                scan_id = self.db.record_scan(
                    source_filename=filename,
                    file_path=str(path),
                    file_hash="",
                    file_size_bytes=path.stat().st_size if path.is_file() else 0,
                    ocr_engine=self.ocr_engine.name,
                    raw_text="",
                    status="ERROR",
                    review_reasons=[str(exc)],
                    invoice_id=None,
                )
            except Exception:
                scan_id = None

            return ProcessingResult(
                source_filename=filename,
                file_path=str(path),
                file_hash="",
                status="ERROR",
                review_reasons=[f"Processing error: {str(exc)}"],
                scan_id=scan_id,
            )

    def process_directory(self, input_dir: Union[str, Path]) -> List[ProcessingResult]:
        """
        Process all supported image files in the target directory.
        Gracefully continues if any single file fails.
        """
        dir_path = Path(input_dir).resolve()
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Input directory does not exist: {dir_path}")

        supported_extensions = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}
        image_files = sorted(
            [f for f in dir_path.iterdir() if f.suffix.lower() in supported_extensions and f.is_file()]
        )

        logger.info(f"Found {len(image_files)} images to process in {dir_path}")
        results: List[ProcessingResult] = []

        for img in image_files:
            res = self.process_file(img)
            results.append(res)

        return results
