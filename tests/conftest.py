"""
Pytest configuration and fixed OCR text fixtures.
Provides deterministic test data independent of external OCR engines.
"""

import pytest
import tempfile
from pathlib import Path
from src.database.db_manager import DatabaseManager

# Fixed OCR texts from actual synthetic samples
FIXED_OCR_VALID_101 = """SYNTHETIC TEST INVOICE
Invoice: TNM-101
Vendor: Acme Office Supplies
Date: 2026-10-01
Currency: INR
Subtotal: 1200.50
Tax: 216.09
Total: 1416.59
"""

FIXED_OCR_COPY_101 = """SYNTHETIC TEST INVOICE
Invoice: TNM-101
Vendor: ACME OFFICE SUPPLIES
Date: 01/10/2026
Currency: INR
Subtotal: 1,200.50
Tax: 216.09
Total: 1,416.59
"""

FIXED_OCR_VALID_102 = """SYNTHETIC TEST INVOICE
Invoice: TNM-102
Vendor: Beta Print Studio
Date: 2026-10-02
Currency: INR
Subtotal: 1500.00
Tax: 270.00
Total: 1770.00
"""

FIXED_OCR_AMBIGUOUS_103 = """SYNTHETIC TEST INVOICE
Invoice: TNM-103
Vendor: Gamma Paper Co
Date: [not supplied]
Currency: INR
Subtotal: 1000.00
Tax: 180.00
Total: 11?0.00
"""

FIXED_OCR_MATH_MISMATCH = """SYNTHETIC TEST INVOICE
Invoice: TNM-999
Vendor: Delta Logistics
Date: 2026-11-05
Currency: INR
Subtotal: 1000.00
Tax: 180.00
Total: 1500.00
"""


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh isolated temporary SQLite database for testing."""
    db_file = tmp_path / "test_invoices.db"
    db = DatabaseManager(db_path=str(db_file))
    return db
