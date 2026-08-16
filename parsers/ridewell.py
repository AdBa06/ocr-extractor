from __future__ import annotations

import re
from statistics import median

from extraction import PageData, build_aor, clean, extract_seater, money, norm_key, notes_with_date
from .common import cell, column, find_table, header_map


def parse_ridewell(pages: list[PageData]) -> list[dict]:
    table, header_index = find_table(pages, ("date", "time", "from", "to", "seater", "total"))
    if table is None:
        return []
    mapping = header_map(table[header_index])
    rows = []
    parsed_raw_rows = table[header_index + 1:]
    correction = _ocr_destination_correction(pages)
    full_text = "\n".join(page.text for page in pages)
    poc_match = re.search(r"\bPOC\s*:\s*([^\n]+)", full_text, re.I)
    comments_text = f"POC: {clean(poc_match.group(1))}" if poc_match else ""
    for row_index, raw in enumerate(parsed_raw_rows):
        source = cell(raw, column(mapping, ("from",)))
        destination_index = column(mapping, ("to",))
        raw_destination = str(raw[destination_index] or "") if destination_index is not None and destination_index < len(raw) else ""
        destination = clean(raw_destination)
        amount = money(cell(raw, column(mapping, ("total",))))
        if not any((source, destination, amount)):
            continue
        date = cell(raw, column(mapping, ("date",)))
        time = cell(raw, column(mapping, ("time",)))
        way_seater = cell(raw, column(mapping, ("way/seater", "seater")))
        aor, review = build_aor(extract_seater(way_seater), time)
        notes = []
        # Normal addresses are multiline too. Multiple postal addresses, or an OCR value
        # printed beneath the last destination cell, indicate Ridewell's correction case.
        suspicious = len(re.findall(r"Singapore\s+\d{6}", raw_destination, re.I)) > 1
        if suspicious:
            review = True
            notes.append("Destination contains multiple printed/corrected values: " + destination)
        if correction and row_index == len(parsed_raw_rows) - 1:
            review = True
            notes.append(f"Destination has two printed values. In-cell/struck value: {destination}. Value printed below table: {correction}")
            destination = f"{destination} | {correction}"
        comments = cell(raw, column(mapping, ("special comments", "comments", "remarks"))) or comments_text
        if any(word.get("source") == "ocr" for page in pages for word in page.words):
            notes.append("Extracted using local OCR")
        rows.append({"aor_title_line_item": aor, "amount": amount, "vendor": "Ridewell Travel",
                     "remarks": comments, "reporting_location": source, "to_location": destination,
                     "needs_review": review, "notes": notes_with_date(notes, date)})
    return rows


def _ocr_destination_correction(pages: list[PageData]) -> str:
    """Find a Ridewell correction printed just below the last ruled To cell."""
    words = [word for page in pages for word in page.words if word.get("source") == "ocr"]
    if not words:
        return ""
    to_header = next((word for word in words if norm_key(word["text"]) == "to"), None)
    from_header = next((word for word in words if norm_key(word["text"]) == "from"), None)
    way_header = next((word for word in words if norm_key(word["text"]).startswith("way")), None)
    date_headers = [word for word in words if norm_key(word["text"]) == "date"]
    if not all((to_header, from_header, way_header)) or not date_headers:
        return ""
    date_header = min(date_headers, key=lambda word: abs(word["top"] - to_header["top"]))
    center = lambda word: (word["x0"] + word["x1"]) / 2
    left = (center(from_header) + center(to_header)) / 2
    right = (center(to_header) + center(way_header)) / 2
    date_x = center(date_header)
    date_words = [word for word in words
                  if abs(center(word) - date_x) < 55
                  and word["top"] > date_header["bottom"]
                  and re.search(r"\d{1,2}[-/]\w{1,9}[-/]\d{2,4}", word["text"])]
    date_words.sort(key=lambda word: word["top"])
    if len(date_words) < 2:
        return ""
    row_centers = [(word["top"] + word["bottom"]) / 2 for word in date_words]
    gaps = [b - a for a, b in zip(row_centers, row_centers[1:]) if b - a > 15]
    row_gap = median(gaps) if gaps else 80
    cutoff = row_centers[-1] + row_gap * 0.48
    section = next((word for word in words if "specialcomments" in norm_key(word["text"])), None)
    section_top = section["top"] if section else cutoff + row_gap
    candidates = [word for word in words
                  if left <= center(word) <= right and cutoff <= word["top"] < section_top]
    candidates.sort(key=lambda word: (word["top"], word["x0"]))
    return clean(" ".join(word["text"] for word in candidates))
