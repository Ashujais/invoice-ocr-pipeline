"""
Validator module for invoice business rules.
Ensures required fields are populated, normalized, and that Subtotal + Tax = Total.
"""

from typing import List
from src.models import RawExtraction, InvoiceRecord, ValidationResult
from src.parser import InvoiceParser


class InvoiceValidator:
    """Validates raw extracted invoice data against business and mathematical rules."""

    @classmethod
    def validate(cls, raw: RawExtraction) -> ValidationResult:
        """
        Validate extracted invoice fields.
        
        Args:
            raw: RawExtraction object containing raw strings from OCR.
            
        Returns:
            ValidationResult with status 'VALID' or 'NEEDS_REVIEW' and reasons.
        """
        errors: List[str] = []

        # 1. Normalize and validate Vendor
        vendor, vendor_norm, vendor_err = InvoiceParser.normalize_vendor(raw.raw_vendor)
        if vendor_err:
            errors.append(vendor_err)

        # 2. Normalize and validate Invoice Number
        inv_num, inv_num_norm, inv_err = InvoiceParser.normalize_invoice_number(raw.raw_invoice_number)
        if inv_err:
            errors.append(inv_err)

        # 3. Normalize and validate Invoice Date
        inv_date, date_err = InvoiceParser.normalize_date(raw.raw_date)
        if date_err:
            errors.append(date_err)

        # 4. Normalize and validate Currency
        currency, curr_err = InvoiceParser.normalize_currency(raw.raw_currency)
        if curr_err:
            errors.append(curr_err)

        # 5. Normalize and validate Subtotal
        subtotal, sub_paise, sub_err = InvoiceParser.normalize_amount(raw.raw_subtotal, "subtotal")
        if sub_err:
            errors.append(sub_err)

        # 6. Normalize and validate Tax
        tax, tax_paise, tax_err = InvoiceParser.normalize_amount(raw.raw_tax, "tax")
        if tax_err:
            errors.append(tax_err)

        # 7. Normalize and validate Total
        total, total_paise, tot_err = InvoiceParser.normalize_amount(raw.raw_total, "total")
        if tot_err:
            errors.append(tot_err)

        # If any field failed normalization, return immediately with collected reasons
        if errors:
            return ValidationResult(
                is_valid=False,
                status="NEEDS_REVIEW",
                errors=errors,
                record=None,
                raw_extraction=raw,
            )

        # 8. Mathematical Integrity Check: Subtotal + Tax == Total
        expected_total = subtotal + tax
        if expected_total != total:
            diff = total - expected_total
            errors.append(
                f"Mathematical mismatch: Subtotal ({subtotal}) + Tax ({tax}) = {expected_total}, "
                f"which does not match Total ({total}) (discrepancy: {diff:+})"
            )
            return ValidationResult(
                is_valid=False,
                status="NEEDS_REVIEW",
                errors=errors,
                record=None,
                raw_extraction=raw,
            )

        # Double check paise arithmetic
        if (sub_paise + tax_paise) != total_paise:
            errors.append(
                f"Integer paise mismatch: {sub_paise} + {tax_paise} != {total_paise}"
            )
            return ValidationResult(
                is_valid=False,
                status="NEEDS_REVIEW",
                errors=errors,
                record=None,
                raw_extraction=raw,
            )

        # Build clean validated record
        record = InvoiceRecord(
            vendor=vendor,
            vendor_normalized=vendor_norm,
            invoice_number=inv_num,
            invoice_number_normalized=inv_num_norm,
            invoice_date=inv_date,
            currency=currency,
            subtotal=subtotal,
            tax=tax,
            total=total,
            subtotal_paise=sub_paise,
            tax_paise=tax_paise,
            total_paise=total_paise,
        )

        return ValidationResult(
            is_valid=True,
            status="VALID",
            errors=[],
            record=record,
            raw_extraction=raw,
        )
