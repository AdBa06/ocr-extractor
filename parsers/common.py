from __future__ import annotations

import re

from extraction import PageData, clean, norm_key


def find_table(pages: list[PageData], required: tuple[str, ...]):
    wanted = tuple(norm_key(item) for item in required)
    for page in pages:
        for table in page.tables:
            for index, row in enumerate(table):
                keys = [norm_key(cell) for cell in row]
                joined = " ".join(keys)
                if all(item in joined for item in wanted):
                    return table, index
    return None, -1


def header_map(row: list[str | None]) -> dict[str, int]:
    return {norm_key(cell): index for index, cell in enumerate(row) if clean(cell)}


def column(mapping: dict[str, int], aliases: tuple[str, ...]) -> int | None:
    for alias in aliases:
        needle = norm_key(alias)
        for key, index in mapping.items():
            if needle == key or needle in key:
                return index
    return None


def cell(row: list[str | None], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return clean(row[index])


def label(text: str, name: str, next_names: tuple[str, ...]) -> str:
    stops = "|".join(re.escape(item) for item in next_names)
    match = re.search(
        rf"{re.escape(name)}\s*:?\s*(.+?)(?=\s*(?:{stops})\s*:|$)",
        text,
        re.I | re.S,
    )
    return clean(match.group(1)) if match else ""

