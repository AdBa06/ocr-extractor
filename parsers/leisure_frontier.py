from __future__ import annotations

import re

from extraction import PageData, build_aor, clean, extract_seater, money, norm_key, notes_with_date
from .common import cell, column, find_table, header_map


def parse_leisure_frontier(pages: list[PageData]) -> list[dict]:
    table, header_index = find_table(pages, ("date", "type", "time", "pickup", "dropoff", "amount"))
    if table is None:
        table = _coordinate_table(pages)
        header_index = 0
    if not table:
        return []
    mapping = header_map(table[header_index])
    rows = []
    for raw in table[header_index + 1:]:
        number = cell(raw, column(mapping, ("no", "s/n")))
        pickup = cell(raw, column(mapping, ("pick-up", "pickup", "from")))
        dropoff = cell(raw, column(mapping, ("drop-off", "dropoff", "to")))
        amount = money(cell(raw, column(mapping, ("amount",))))
        if not any((pickup, dropoff, amount)) or (number and not re.search(r"\d", number)):
            continue
        date = cell(raw, column(mapping, ("date",)))
        time = cell(raw, column(mapping, ("time",)))
        vehicle = cell(raw, column(mapping, ("type",)))
        aor, review = build_aor(extract_seater(vehicle), time)
        rows.append({"aor_title_line_item": aor, "amount": amount,
                     "vendor": "Leisure Frontier", "remarks": "",
                     "reporting_location": pickup, "to_location": dropoff,
                     "needs_review": review, "notes": notes_with_date([], date)})
    return rows


def _coordinate_table(pages: list[PageData]) -> list[list[str]]:
    """Recover Leisure's borderless quotation table from word coordinates."""
    for page in pages:
        words = page.words
        keys = {norm_key(word.get("text", "")) for word in words}
        if not {"date", "time", "pickup", "dropoff", "qty", "price", "amount"}.issubset(keys):
            continue
        date_words = [word for word in words if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", word.get("text", ""))
                      and word.get("top", 0) > 0]
        rows = [["DATE", "TYPE OF SERVICE", "TIME", "PICK-UP POINT", "DROP-OFF POINT", "QTY", "PRICE (S$)", "AMOUNT (S$)"]]
        for date_word in sorted(date_words, key=lambda word: word["top"]):
            center_y = (date_word["top"] + date_word["bottom"]) / 2
            line = sorted([word for word in words
                           if abs((word["top"] + word["bottom"]) / 2 - center_y) <= 3],
                          key=lambda word: word["x0"])
            date_index = line.index(date_word)
            time_index = next((index for index in range(date_index + 1, len(line))
                               if re.fullmatch(r"\d{3,4}", line[index]["text"])), None)
            money_indices = [index for index, word in enumerate(line)
                             if re.fullmatch(r"\d[\d,]*\.\d{2}", word["text"])]
            if time_index is None or len(money_indices) < 2:
                continue
            price_index, amount_index = money_indices[-2:]
            qty_index = price_index - 1
            if qty_index <= time_index:
                continue
            vehicle = clean(" ".join(word["text"] for word in line[date_index + 1:time_index]))
            locations = line[time_index + 1:qty_index]
            if len(locations) < 2:
                continue
            split_index = max(range(1, len(locations)),
                              key=lambda index: locations[index]["x0"] - locations[index - 1]["x1"])
            pickup = clean(" ".join(word["text"] for word in locations[:split_index]))
            dropoff = clean(" ".join(word["text"] for word in locations[split_index:]))
            rows.append([date_word["text"], vehicle, line[time_index]["text"], pickup, dropoff,
                         line[qty_index]["text"], line[price_index]["text"], line[amount_index]["text"]])
        return rows
    return []
