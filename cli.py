#!/usr/bin/env python3
"""
Command Line Interface for Invoice OCR, Validation, and Storage Pipeline.
"""

import argparse
import sys
import urllib.request
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ocr.factory import get_ocr_engine
from src.database.db_manager import DatabaseManager
from src.pipeline import InvoicePipeline
from src.reporter import Reporter

FIXTURE_URLS = {
    "invoice-101.png": "https://thenightmarketer.com/client/hiring/fixtures/invoice-101.png",
    "invoice-102.png": "https://thenightmarketer.com/client/hiring/fixtures/invoice-102.png",
    "invoice-101-copy.png": "https://thenightmarketer.com/client/hiring/fixtures/invoice-101-copy.png",
    "invoice-103-review.png": "https://thenightmarketer.com/client/hiring/fixtures/invoice-103-review.png",
}


def cmd_download_fixtures(args: argparse.Namespace) -> int:
    """Download the synthetic test fixtures into the target directory."""
    dest_dir = Path(args.dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading fixtures to {dest_dir}...")

    for filename, url in FIXTURE_URLS.items():
        target = dest_dir / filename
        if target.exists() and not args.force:
            print(f"  [Exists] {filename}")
            continue
        try:
            print(f"  [Downloading] {filename} from {url}...")
            urllib.request.urlretrieve(url, target)
            print(f"  [Done] {filename}")
        except Exception as e:
            print(f"  [Error] Failed to download {filename}: {e}", file=sys.stderr)
            return 1

    print("All fixtures downloaded successfully.")
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    """Process a directory of invoice images through the pipeline."""
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"Error: Input directory does not exist: {input_dir}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    raw_ocr_dir = output_dir / "raw_ocr"
    raw_ocr_dir.mkdir(parents=True, exist_ok=True)

    print(f"Initializing database at: {args.db_path}")
    db = DatabaseManager(db_path=args.db_path)

    print(f"Initializing OCR engine ('{args.engine}')...")
    try:
        engine = get_ocr_engine(engine_name=args.engine, tesseract_cmd=args.tesseract_cmd)
        print(f"Using OCR engine: {engine.name}")
    except Exception as e:
        print(f"Failed to initialize OCR engine: {e}", file=sys.stderr)
        return 1

    pipeline = InvoicePipeline(
        ocr_engine=engine,
        db_manager=db,
        raw_ocr_dir=raw_ocr_dir,
    )

    print(f"\nProcessing invoice images from: {input_dir}")
    results = pipeline.process_directory(input_dir)

    if not results:
        print("No image files found to process.")
        return 0

    # Print terminal summary
    Reporter.print_terminal_summary(results)

    # Export JSON report
    json_path = output_dir / "review_report.json"
    Reporter.generate_json_report(results, json_path)
    print(f"JSON review report written to: {json_path}")

    # Export CSV report
    csv_path = output_dir / "review_report.csv"
    Reporter.generate_csv_report(results, csv_path)
    print(f"CSV review report written to:  {csv_path}")
    print(f"Raw OCR text files saved to:  {raw_ocr_dir}")

    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Print current database state: saved invoices and scan audit history."""
    db = DatabaseManager(db_path=args.db_path)
    invoices = db.get_all_invoices()
    scans = db.get_all_scans()

    print("\n" + "=" * 80)
    print(f"DATABASE AUDIT REPORT: {args.db_path}")
    print("=" * 80)

    print(f"\n1. Invoices Table ({len(invoices)} unique valid records):")
    if not invoices:
        print("   (No invoices stored yet)")
    else:
        print(f"   {'ID':<4} | {'Vendor':<24} | {'Invoice #':<12} | {'Date':<10} | {'Total':<12} | {'Paise'}")
        print("   " + "-" * 75)
        for inv in invoices:
            print(
                f"   {inv['id']:<4} | {inv['vendor']:<24} | {inv['invoice_number']:<12} | "
                f"{inv['invoice_date']:<10} | {inv['currency']} {inv['total_decimal']:<8} | {inv['total_paise']}"
            )

    print(f"\n2. Invoice Scans Table ({len(scans)} scan trace records):")
    if not scans:
        print("   (No scans recorded yet)")
    else:
        print(f"   {'Scan ID':<7} | {'Filename':<24} | {'Status':<12} | {'Invoice ID':<10} | {'Timestamp'}")
        print("   " + "-" * 75)
        for s in scans:
            inv_id_str = str(s['invoice_id']) if s['invoice_id'] is not None else "-"
            print(f"   {s['id']:<7} | {s['source_filename']:<24} | {s['status']:<12} | {inv_id_str:<10} | {s['scanned_at']}")

    print("\n" + "=" * 80 + "\n")
    return 0


def cmd_init_db(args: argparse.Namespace) -> int:
    """Initialize or reset the database."""
    db = DatabaseManager(db_path=args.db_path)
    print(f"Database schema initialized at: {db.db_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Invoice OCR Extraction, Business Validation, and Storage CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Process command
    p_proc = subparsers.add_parser("process", help="Extract, validate, and store invoices from images")
    p_proc.add_argument(
        "-i", "--input-dir", default="./fixtures", help="Directory with invoice images (default: ./fixtures)"
    )
    p_proc.add_argument(
        "-o", "--output-dir", default="./output", help="Directory for reports and raw OCR text (default: ./output)"
    )
    p_proc.add_argument(
        "-d", "--db-path", default="invoices.db", help="SQLite database path (default: invoices.db)"
    )
    p_proc.add_argument(
        "--engine", choices=["auto", "rapidocr", "tesseract"], default="auto",
        help="OCR engine to use (default: auto)"
    )
    p_proc.add_argument(
        "--tesseract-cmd", default=None, help="Explicit path to tesseract binary"
    )

    # Report command
    p_rep = subparsers.add_parser("report", help="Inspect stored database invoices and scan audit log")
    p_rep.add_argument(
        "-d", "--db-path", default="invoices.db", help="SQLite database path (default: invoices.db)"
    )

    # Init-db command
    p_init = subparsers.add_parser("init-db", help="Initialize the database schema")
    p_init.add_argument(
        "-d", "--db-path", default="invoices.db", help="SQLite database path (default: invoices.db)"
    )

    # Download fixtures command
    p_dl = subparsers.add_parser("download-fixtures", help="Download synthetic sample invoices")
    p_dl.add_argument(
        "--dest", default="./fixtures", help="Target directory for downloaded fixtures"
    )
    p_dl.add_argument(
        "--force", action="store_true", help="Overwrite existing downloaded files"
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "process": cmd_process,
        "report": cmd_report,
        "init-db": cmd_init_db,
        "download-fixtures": cmd_download_fixtures,
    }

    handler = dispatch.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
