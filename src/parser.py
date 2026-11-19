"""
Invoice raw text parser and field normalizer.
Extracts invoice fields from OCR text and normalizes dates, currencies, and amounts.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple
from src.models import RawExtraction


class InvoiceParser:
    """Parses raw OCR text into structured raw fields and normalizes them."""

    # Regex patterns for key fields with line-anchored multiline matching
    INVOICE_PATTERN = re.compile(
        r"(?im)^\s*(?:Invoice(?:\s*Number|\s*No|\s*#|\s*ID)?|Inv(?:\s*No|\s*#)?)\s*[:=\-]\s*([^\r\n]+)"
    )
    VENDOR_PATTERN = re.compile(
        r"(?im)^\s*(?:Vendor(?:\s*Name)?|Supplier|Billed\s*By|From)\s*[:=\-]\s*([^\r\n]+)"
    )
    DATE_PATTERN = re.compile(
        r"(?im)^\s*(?:Invoice\s*Date|Date)\s*[:=\-]\s*([^\r\n]+)"
    )
    CURRENCY_PATTERN = re.compile(
        r"(?im)^\s*(?:Currency)\s*[:=\-]\s*([^\r\n]+)"
    )
    SUBTOTAL_PATTERN = re.compile(
        r"(?im)^\s*(?:Subtotal|Sub\s*-?\s*Total|Net\s*Amount)\s*[:=\-]\s*([^\r\n]+)"
    )
    TAX_PATTERN = re.compile(
        r"(?im)^\s*(?:Tax(?:\s*Amount)?|VAT|GST)\s*[:=\-]\s*([^\r\n]+)"
    )
    TOTAL_PATTERN = re.compile(
        r"(?im)^\s*(?:Total(?:\s*Amount)?|Gross\s*Amount|Grand\s*Total)\s*[:=\-]\s*([^\r\n]+)"
    )

    CURRENCY_SYMBOLS = {
        "₹": "INR",
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
    }

    MISSING_SENTINELS = {
        "[not supplied]",
        "not supplied",
        "missing",
        "n/a",
        "na",
        "none",
        "null",
        "unknown",
        "-",
        "",
    }

    @classmethod
    def parse_raw_text(cls, raw_text: str) -> RawExtraction:
        """Extract unvalidated raw strings from OCR text."""
        raw_inv = cls._extract_first(cls.INVOICE_PATTERN, raw_text)
        raw_vendor = cls._extract_first(cls.VENDOR_PATTERN, raw_text)
        raw_date = cls._extract_first(cls.DATE_PATTERN, raw_text)
        raw_curr = cls._extract_first(cls.CURRENCY_PATTERN, raw_text)
        raw_sub = cls._extract_first(cls.SUBTOTAL_PATTERN, raw_text)
        raw_tax = cls._extract_first(cls.TAX_PATTERN, raw_text)
        raw_tot = cls._extract_first(cls.TOTAL_PATTERN, raw_text)

        # Fallback currency detection if not in explicit 'Currency:' line
        if not raw_curr:
            for symbol, code in cls.CURRENCY_SYMBOLS.items():
                if symbol in raw_text:
                    raw_curr = code
                    break
            if not raw_curr and "INR" in raw_text.upper():
                raw_curr = "INR"

        return RawExtraction(
            raw_text=raw_text,
            raw_invoice_number=raw_inv,
            raw_vendor=raw_vendor,
            raw_date=raw_date,
            raw_currency=raw_curr,
            raw_subtotal=raw_sub,
            raw_tax=raw_tax,
            raw_total=raw_tot,
        )

    @staticmethod
    def _extract_first(pattern: re.Pattern, text: str) -> Optional[str]:
        match = pattern.search(text)
        if match:
            val = match.group(1).strip()
            # Clean up trailing punctuation if any
            return val.strip()
        return None

    @classmethod
    def normalize_vendor(cls, raw_vendor: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Normalize vendor string.
        
        Returns:
            (display_vendor, normalized_key, error_message)
        """
        if not raw_vendor or raw_vendor.strip().lower() in cls.MISSING_SENTINELS:
            return None, None, "Missing required field: vendor"

        cleaned = " ".join(raw_vendor.strip().split())
        normalized_key = cleaned.lower()
        return cleaned, normalized_key, None

    @classmethod
    def normalize_invoice_number(cls, raw_num: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Normalize invoice number.
        
        Returns:
            (display_num, normalized_key, error_message)
        """
        if not raw_num or raw_num.strip().lower() in cls.MISSING_SENTINELS:
            return None, None, "Missing required field: invoice_number"

        cleaned = raw_num.strip()
        # Strip redundant prefix if captured (e.g. 'Invoice: TNM-101' -> 'TNM-101')
        cleaned = re.sub(r"(?i)^(?:invoice(?:\s*#|\s*no)?|inv(?:\s*#|\s*no)?)\s*[:=\-]?\s*", "", cleaned).strip()
        normalized_key = cleaned.upper()
        return cleaned, normalized_key, None

    @classmethod
    def normalize_date(cls, raw_date: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Normalize date string into ISO-8601 'YYYY-MM-DD'.
        
        Returns:
            (iso_date_string, error_message)
        """
        if not raw_date or raw_date.strip().lower() in cls.MISSING_SENTINELS:
            sentinel = raw_date.strip() if raw_date else "missing"
            return None, f"Missing required field: invoice_date ({sentinel!r})"

        cleaned = raw_date.strip()

        # Try various standard date formats
        # Prioritize day-first for slash/hyphen dates common in IN/UK formats (e.g. 01/10/2026 -> Oct 1, 2026)
        date_formats = [
            "%Y-%m-%d",       # 2026-10-01
            "%d/%m/%Y",       # 01/10/2026
            "%d-%m-%Y",       # 01-10-2026
            "%d.%m.%Y",       # 01.10.2026
            "%Y/%m/%d",       # 2026/10/01
            "%m/%d/%Y",       # 10/01/2026
            "%d %b %Y",       # 01 Oct 2026
            "%d %B %Y",       # 01 October 2026
            "%b %d, %Y",      # Oct 01, 2026
        ]

        for fmt in date_formats:
            try:
                parsed_dt = datetime.strptime(cleaned, fmt)
                return parsed_dt.strftime("%Y-%m-%d"), None
            except ValueError:
                continue

        return None, f"Ambiguous or invalid date format: {raw_date!r}"

    @classmethod
    def normalize_currency(cls, raw_curr: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Normalize currency to ISO code (e.g., INR).
        
        Returns:
            (currency_code, error_message)
        """
        if not raw_curr or raw_curr.strip().lower() in cls.MISSING_SENTINELS:
            return None, "Missing required field: currency"

        cleaned = raw_curr.strip().upper()
        if cleaned in cls.CURRENCY_SYMBOLS:
            cleaned = cls.CURRENCY_SYMBOLS[cleaned]

        if not re.match(r"^[A-Z]{3}$", cleaned):
            return None, f"Ambiguous or invalid currency code: {raw_curr!r}"

        return cleaned, None

    @classmethod
    def normalize_amount(cls, raw_amt: Optional[str], field_name: str) -> Tuple[Optional[Decimal], Optional[int], Optional[str]]:
        """
        Normalize monetary amount into Decimal and integer paise.
        Detects ambiguous characters (like '?'), missing values, or invalid formats.
        
        Returns:
            (decimal_amount, paise_amount, error_message)
        """
        if not raw_amt or raw_amt.strip().lower() in cls.MISSING_SENTINELS:
            return None, None, f"Missing required field: {field_name}"

        cleaned = raw_amt.strip()

        # Remove currency symbol prefixes/suffixes if attached
        for sym in list(cls.CURRENCY_SYMBOLS.keys()) + ["INR", "USD", "EUR", "GBP", "Rs.", "Rs"]:
            cleaned = cleaned.replace(sym, "").strip()

        # Remove thousands separators (commas)
        cleaned = cleaned.replace(",", "")

        # Check for ambiguous / unrecognized OCR artifacts (e.g. '11?0.00')
        if not re.match(r"^\d+(\.\d{1,2})?$", cleaned):
            return None, None, f"Ambiguous or unparseable amount for {field_name}: {raw_amt!r}"

        try:
            dec = Decimal(cleaned).quantize(Decimal("0.01"))
            if dec < 0:
                return None, None, f"Negative amount not permitted for {field_name}: {raw_amt!r}"
            paise = int(dec * 100)
            return dec, paise, None
        except (InvalidOperation, ValueError):
            return None, None, f"Invalid decimal representation for {field_name}: {raw_amt!r}"
