from __future__ import annotations

import config
import re
from extraction import PageData, extract_oa_number, normalize_oa_number
from parsers import PARSERS


def detect_vendor(pages: list[PageData]) -> str | None:
    page_one = pages[0].text.upper() if pages else ""
    for signature, parser_name in config.VENDOR_SIGNATURES.items():
        if signature in page_one:
            return parser_name
    # Some generated Atlantic PDFs render the company masthead as outlines/image,
    # leaving the otherwise searchable quotation body without the vendor name.
    if re.search(r"\bAT/CQ/\d+", page_one) and "LINE ITEM" in page_one:
        return "atlantic"
    return None


def extract_rows(pages: list[PageData], source_file: str, need_by_date: str = "",
                 gr_date: str = "", po_number: str = "") -> list[dict]:
    if pages and not any(page.text.strip() for page in pages):
        return [_finalize({}, source_file, need_by_date, gr_date, po_number,
                          "This PDF is image-only and local OCR could not recover readable text.",
                          True)]
    vendor = detect_vendor(pages)
    if vendor is None:
        return [_finalize({}, source_file, need_by_date, gr_date, po_number,
                          "Vendor signature not recognised", True)]
    parsed = PARSERS[vendor](pages)
    if not parsed:
        return [_finalize({}, source_file, need_by_date, gr_date, po_number,
                          f"{vendor.replace('_', ' ').title()} detected, but no rows were parsed", True)]
    invoice_oa = extract_oa_number(pages)
    for row in parsed:
        row["po_number"] = normalize_oa_number(row.get("po_number", "")) or invoice_oa
    return [_finalize(row, source_file, need_by_date, gr_date, po_number) for row in parsed]


def _finalize(row: dict, source_file: str, need_by_date: str, gr_date: str,
              po_number: str, note: str = "", review: bool = False) -> dict:
    result = {column: "" for column in config.OUTPUT_COLUMNS}
    result.update({key: value for key, value in row.items() if key in result})
    result["need_by_date"] = need_by_date
    result["gr_date"] = gr_date
    result["po_number"] = normalize_oa_number(row.get("po_number") or po_number)
    result["conduct_name"] = row.get("conduct_name", "")
    result["source_file"] = source_file
    existing_notes = row.get("notes", "")
    result["notes"] = "; ".join(part for part in (existing_notes, note) if part)
    missing_external = [name for name in ("need_by_date", "gr_date", "po_number") if not result[name]]
    if missing_external:
        suffix = "Missing external field(s): " + ", ".join(missing_external)
        result["notes"] = "; ".join(part for part in (result["notes"], suffix) if part)
    result["needs_review"] = bool(row.get("needs_review") or review or missing_external)
    result["review_fields"] = missing_external
    return result
