from __future__ import annotations

import re

from extraction import PageData, clean, money, notes_with_date
from .common import label


LABELS = ("PICKUP TIME", "PICKUP POINT", "DROPOFF POINT", "POC", "LINE ITEM", "UNIT PRICE")


def parse_atlantic(pages: list[PageData]) -> list[dict]:
    text = "\n".join(page.text for page in pages)
    pickup_match = re.search(r"(?m)^PICKUP\s+POINT\s*:\s*([^\n]+)", text, re.I)
    dropoff_match = re.search(r"(?m)^DROPOFF\s+POINT\s*:\s*([^\n]+)", text, re.I)
    poc_match = re.search(r"(?m)^POC\s*:\s*([^\n]+)", text, re.I)
    pickup = clean(pickup_match.group(1)) if pickup_match else ""
    dropoff = clean(dropoff_match.group(1)) if dropoff_match else ""
    poc = clean(poc_match.group(1)) if poc_match else ""
    line_item_match = re.search(r"(\[Year\s*2\]\s*\[Cat\s*A\].*?(?:Non-?Peak|Peak))", text, re.I | re.S)
    line_item = clean(line_item_match.group(1)) if line_item_match else label(text, "LINE ITEM", LABELS)
    price_match = re.search(r"UNIT\s*PRICE.*?(\$\s*[\d,]+(?:\.\d{1,2})?)", text, re.I | re.S)
    if not price_match:
        price_match = re.search(r"@\s*(\$\s*[\d,]+(?:\.\d{1,2})?)", text, re.I)
    amount = money(price_match.group(1)).replace("$ ", "$") if price_match else ""
    date_match = re.search(r"(?m)^\s*(?:\d+\s+)?(\d{1,2}\s+[A-Z]+\s+\d{4})\s*\(", text, re.I)
    review = not all((pickup, dropoff, line_item, amount))
    notes = [] if not review else ["One or more Atlantic fields could not be extracted"]
    return [{"aor_title_line_item": line_item, "amount": amount, "vendor": "Atlantic Travel",
             "remarks": poc, "reporting_location": pickup, "to_location": dropoff,
             "needs_review": review,
             "notes": notes_with_date(notes, date_match.group(1) if date_match else "")}]
