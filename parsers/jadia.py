from __future__ import annotations

import re

from extraction import PageData, clean, money, notes_with_date
from .common import label


JADIA_LABELS = ("ORDER NO", "DATE", "FROM", "TO", "TIME", "TRANSPORT CHARGE", "AMOUNT")
JADIA_AOR_TITLE = (
    "5 Ton Lorry [With Driver] (Hourly Rental 0800-1800 Hrs of Next Day, "
    "Min 4 Hrs Charge) (1 Hr = 1 Job) (Normal/Urgent)"
)


def parse_jadia(pages: list[PageData]) -> list[dict]:
    invoice_pages = [page for page in pages if re.search(r"TAX\s+INVOICE", page.text, re.I)]
    text = "\n".join(page.text for page in (invoice_pages or pages[:1]))
    order_match = re.search(r"ORDER\s+NO\s*\.?\s*:\s*(OA[\w-]+)", text, re.I)
    # One Jadia description contains a single order number followed by multiple
    # DATE/FROM/TO/TIME/TRANSPORT CHARGE trip groups.
    starts = list(re.finditer(r"(?m)^DATE\s*:\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text, re.I))
    rows = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[start.start():end]
        block = re.split(r"(?m)^[•'\s]*(?:Payments|Notes\s*:|SUB-?TOTAL)", block, maxsplit=1, flags=re.I)[0]
        date = label(block, "DATE", JADIA_LABELS)
        source = label(block, "FROM", JADIA_LABELS)
        destination = label(block, "TO", JADIA_LABELS)
        charge_match = re.search(r"(?m)^TRANSPORT\s+CHARGE[^\n]*(?:\n|$)", block, re.I)
        charge_line = charge_match.group(0) if charge_match else ""
        printed_amounts = re.findall(r"\b\d[\d,]*\.\d{2}\b", charge_line)
        amount = money(printed_amounts[-1]) if printed_amounts else ""
        notes = []
        if any(word.get("source") == "ocr" for page in invoice_pages for word in page.words):
            notes.append("Extracted using local OCR")
        rows.append({"aor_title_line_item": JADIA_AOR_TITLE, "amount": amount, "vendor": "Jadia Logistics",
                     "po_number": order_match.group(1).upper() if order_match else "",
                     "remarks": "", "reporting_location": source, "to_location": destination,
                     "needs_review": False,
                     "notes": notes_with_date(notes, date)})
    return rows
