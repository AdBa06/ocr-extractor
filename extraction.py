from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import datetime
from io import BytesIO
from typing import Any

import config


@dataclass(frozen=True)
class PageData:
    number: int
    text: str
    tables: list[list[list[str | None]]] = field(default_factory=list)
    words: list[dict[str, Any]] = field(default_factory=list)


def read_pdf(data: bytes) -> list[PageData]:
    import pdfplumber
    from local_ocr import ocr_page

    pages: list[PageData] = []
    ocr_pdf = None
    with pdfplumber.open(BytesIO(data)) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            words = page.extract_words(keep_blank_chars=False, use_text_flow=True) or []
            if config.OCR_ENABLED and not text.strip():
                import pypdfium2 as pdfium

                if ocr_pdf is None:
                    ocr_pdf = pdfium.PdfDocument(data)
                image = ocr_pdf[number - 1].render(scale=config.OCR_DPI / 72).to_pil()
                text, tables, words = ocr_page(image)
            pages.append(PageData(number, text, tables, words))
    return pages


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def norm_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean(value).lower())


def parse_time(value: str) -> str | None:
    value = clean(value).upper().replace(".", "")
    match = re.search(r"(?<!\d)(\d{1,2})[:.]?(\d{2})\s*(AM|PM)?(?!\d)", value)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    suffix = match.group(3)
    if minute > 59 or hour > 23:
        return None
    if suffix:
        if hour > 12 or hour == 0:
            return None
        if suffix == "PM" and hour != 12:
            hour += 12
        elif suffix == "AM" and hour == 12:
            hour = 0
    return f"{hour:02d}{minute:02d}"


def peak_label(value: str) -> tuple[str, bool]:
    time = parse_time(value)
    if time is None:
        return "", True
    return (
        "Peak" if any(start <= time <= end for start, end in config.PEAK_WINDOWS) else "Non-Peak",
        False,
    )


def extract_seater(value: str) -> str:
    patterns = (r"(\d{1,3})\s*(?:-\s*)?seater", r"\b\d+\s*[wW]\s*/\s*(\d{1,3})\s*[sS]\b")
    for pattern in patterns:
        match = re.search(pattern, value, re.I)
        if match:
            return str(int(match.group(1)))
    return ""


def build_aor(seater: str, time: str) -> tuple[str, bool]:
    peak, review = peak_label(time)
    if not seater:
        return "", True
    title = (
        f"{config.AOR_PREFIX} {seater} Seater {config.AOR_VEHICLE}, "
        f"{config.AOR_TRIP}, {config.AOR_DISTANCE}, {peak}"
    )
    return title, review


def normalize_date(value: str) -> str:
    raw = clean(value).replace(",", "")
    raw = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", raw, flags=re.I)
    for fmt in (
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y",
        "%d-%b-%y", "%d-%B-%y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
    ):
        try:
            return datetime.strptime(raw, fmt).strftime("%d/%m/%Y")
        except ValueError:
            pass
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", raw)
    if match:
        day, month, year = match.groups()
        if len(year) == 2:
            year = "20" + year
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return raw


def money(value: str) -> str:
    value = clean(value)
    match = re.search(r"(?<!\w)(S?\$)?\s*([\d,]+(?:\.\d{1,2})?)(?!\d)", value, re.I)
    if not match:
        return value
    try:
        number = Decimal(match.group(2).replace(",", ""))
    except InvalidOperation:
        return value
    return f"${number:.2f}"


def normalize_oa_number(value: str) -> str:
    """Convert an OA/order/quotation reference to OA followed by its digits."""
    value = clean(value).upper()
    start = value.find("2")
    if start < 0:
        return ""
    digits = re.sub(r"\D", "", value[start:])
    return f"OA{digits}" if len(digits) >= 6 else ""


def extract_oa_number(pages: list[PageData]) -> str:
    """Read an order or quotation reference and normalize it as an OA number."""
    text = "\n".join(page.text for page in pages)
    patterns = (
        r"(?im)^.*?ORDER\s+NO\.?\s*:\s*([A-Z0-9][A-Z0-9/-]*)",
        r"(?im)^.*?QUOTATION\s*(?:NO\.?|#)\s*:?\s*([A-Z0-9][A-Z0-9/-]*)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            normalized = normalize_oa_number(match.group(1))
            if normalized:
                return normalized
    return ""


def table_rows(pages: list[PageData]):
    for page in pages:
        for table in page.tables:
            for index, row in enumerate(table):
                yield page.number, index, [clean(cell) for cell in row]


def notes_with_date(notes: list[str], date: str) -> str:
    if date:
        notes.insert(0, f"Extracted service date: {normalize_date(date)}")
    return "; ".join(item for item in notes if item)
