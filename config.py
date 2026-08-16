"""User-tuneable extraction constants."""

PEAK_WINDOWS = [("0630", "0900"), ("1700", "2000")]

AOR_PREFIX = "[Year 2] [Cat A]"
AOR_VEHICLE = "Diesel Bus"
AOR_TRIP = "1-Way Trip"
AOR_DISTANCE = "Up to 20km"

VENDOR_SIGNATURES = {
    "TONG TAR": "tong_tar",
    "LEISURE FRONTIER": "leisure_frontier",
    "ATLANTIC TRAVEL": "atlantic",
    "RIDEWELL": "ridewell",
    "JADIA": "jadia",
}

OUTPUT_COLUMNS = [
    "aor_title_line_item",
    "amount",
    "need_by_date",
    "gr_date",
    "vendor",
    "po_number",
    "remarks",
    "conduct_name",
    "reporting_location",
    "to_location",
]

# OCR is the default fallback only when a page has no usable PDF text layer.
# The bundled RapidOCR models run locally; raising DPI improves small invoice text
# at the cost of processing time.
OCR_ENABLED = True
OCR_DPI = 129.6
OCR_MIN_CONFIDENCE = 0.55
