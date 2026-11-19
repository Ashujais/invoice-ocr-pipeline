"""
Report generator for OCR and invoice validation results.
Generates structured JSON and CSV reports along with terminal summary tables.
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Union
from src.models import ProcessingResult


class Reporter:
    """Generates evaluation and audit reports in JSON and CSV formats."""

    @staticmethod
    def generate_json_report(
        results: List[ProcessingResult], output_file: Union[str, Path]
    ) -> Path:
        """Export processing results as structured JSON."""
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        summary_counts: Dict[str, int] = {
            "total_scanned": len(results),
            "valid": sum(1 for r in results if r.status == "VALID"),
            "duplicate": sum(1 for r in results if r.status == "DUPLICATE"),
            "needs_review": sum(1 for r in results if r.status == "NEEDS_REVIEW"),
            "error": sum(1 for r in results if r.status == "ERROR"),
        }

        report_data = {
            "summary": summary_counts,
            "results": [r.to_dict() for r in results],
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        return out_path

    @staticmethod
    def generate_csv_report(
        results: List[ProcessingResult], output_file: Union[str, Path]
    ) -> Path:
        """Export processing results as flat CSV."""
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "source_filename",
            "file_hash",
            "status",
            "invoice_id",
            "scan_id",
            "vendor",
            "invoice_number",
            "invoice_date",
            "currency",
            "subtotal",
            "tax",
            "total",
            "review_reasons",
            "raw_text",
        ]

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for r in results:
                rec = r.invoice_record
                raw = r.raw_extraction
                vendor_val = rec.vendor if rec else (raw.raw_vendor if raw else "")
                inv_no_val = rec.invoice_number if rec else (raw.raw_invoice_number if raw else "")
                date_val = rec.invoice_date if rec else (raw.raw_date if raw else "")
                curr_val = rec.currency if rec else (raw.raw_currency if raw else "")
                sub_val = str(rec.subtotal) if rec else (raw.raw_subtotal if raw else "")
                tax_val = str(rec.tax) if rec else (raw.raw_tax if raw else "")
                tot_val = str(rec.total) if rec else (raw.raw_total if raw else "")

                row = {
                    "source_filename": r.source_filename,
                    "file_hash": r.file_hash,
                    "status": r.status,
                    "invoice_id": r.invoice_id if r.invoice_id is not None else "",
                    "scan_id": r.scan_id if r.scan_id is not None else "",
                    "vendor": vendor_val,
                    "invoice_number": inv_no_val,
                    "invoice_date": date_val,
                    "currency": curr_val,
                    "subtotal": sub_val,
                    "tax": tax_val,
                    "total": tot_val,
                    "review_reasons": " | ".join(r.review_reasons) if r.review_reasons else "",
                    "raw_text": r.raw_text.replace("\n", " "),
                }
                writer.writerow(row)

        return out_path

    @staticmethod
    def print_terminal_summary(results: List[ProcessingResult]) -> None:
        """Print clean ASCII summary table to stdout."""
        header = f"{'Source File':<25} | {'Status':<12} | {'Invoice #':<10} | {'Vendor':<22} | {'Total':<10} | {'Notes / Reasons'}"
        divider = "-" * len(header)
        print("\n" + divider)
        print("INVOICE PROCESSING REPORT")
        print(divider)
        print(header)
        print(divider)

        for r in results:
            rec = r.invoice_record
            raw = r.raw_extraction
            inv_no = rec.invoice_number if rec else (raw.raw_invoice_number if raw else "-")
            vendor = rec.vendor if rec else (raw.raw_vendor if raw else "-")
            if len(vendor) > 22:
                vendor = vendor[:20] + ".."
            total = f"{rec.currency} {rec.total}" if rec else (f"Raw: {raw.raw_total}" if (raw and raw.raw_total) else "-")
            notes = "; ".join(r.review_reasons) if r.review_reasons else "OK"
            if len(notes) > 50:
                notes = notes[:47] + "..."
            print(f"{r.source_filename:<25} | {r.status:<12} | {inv_no:<12} | {vendor:<22} | {total:<12} | {notes}")

        print(divider)
        valid_cnt = sum(1 for r in results if r.status == "VALID")
        dup_cnt = sum(1 for r in results if r.status == "DUPLICATE")
        rev_cnt = sum(1 for r in results if r.status == "NEEDS_REVIEW")
        err_cnt = sum(1 for r in results if r.status == "ERROR")
        print(f"Summary: Total: {len(results)} | Valid: {valid_cnt} | Duplicates: {dup_cnt} | Needs Review: {rev_cnt} | Errors: {err_cnt}")
        print(divider + "\n")
