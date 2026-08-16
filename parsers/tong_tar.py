from __future__ import annotations

import re

from extraction import PageData, build_aor, extract_seater, money, notes_with_date
from .common import cell, column, find_table, header_map


def parse_tong_tar(pages: list[PageData]) -> list[dict]:
    table, header_index = find_table(pages, ("date", "time", "pick", "drop", "unitprice"))
    if table is None:
        return []
    mapping = header_map(table[header_index])
    rows = []
    full_text = "\n".join(page.text for page in pages)
    multiple = bool(re.search(r"\b\d+\s*[x×]\s*\d+\s*-?\s*seater", full_text, re.I))
    for raw in table[header_index + 1:]:
        date = cell(raw, column(mapping, ("date",)))
        time = cell(raw, column(mapping, ("time",)))
        pickup = cell(raw, column(mapping, ("pick up", "pickup", "from")))
        dropoff = cell(raw, column(mapping, ("drop off", "dropoff", "to")))
        bus_type = cell(raw, column(mapping, ("bus type", "type")))
        amount = money(cell(raw, column(mapping, ("unit price", "price"))))
        if not any((pickup, dropoff, amount)):
            continue
        seater = extract_seater(bus_type + " " + full_text)
        aor, review = build_aor(seater, time)
        multiple_row = multiple or bool(re.search(r"\b\d+\s*[x×]\s*\d+", bus_type, re.I))
        non_bus = bool(bus_type and not re.search(r"bus|seater", bus_type, re.I))
        notes = []
        if multiple_row:
            notes.append("Invoice indicates multiple buses; verify the per-line amount against the grand total")
        if non_bus:
            aor, review = "", True
            notes.append(f"Non-standard vehicle description: {bus_type}")
        if any(word.get("source") == "ocr" for page in pages for word in page.words):
            notes.append("Extracted using local OCR")
        rows.append({"aor_title_line_item": aor, "amount": amount, "vendor": "Tong Tar",
                     "remarks": "", "reporting_location": pickup, "to_location": dropoff,
                     "needs_review": review or multiple_row, "notes": notes_with_date(notes, date)})
    return rows
