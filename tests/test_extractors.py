import unittest
from pathlib import Path

from extraction import (PageData, build_aor, extract_oa_number, money,
                        normalize_date, normalize_oa_number, peak_label, read_pdf)
from parsers.atlantic import parse_atlantic
from parsers.jadia import parse_jadia
from parsers.leisure_frontier import parse_leisure_frontier
from parsers.ridewell import parse_ridewell
from parsers.tong_tar import parse_tong_tar
from service import extract_rows


def page(text="", table=None):
    return PageData(1, text, [table] if table else [], [])


class RulesTest(unittest.TestCase):
    def test_peak_windows_are_inclusive(self):
        self.assertEqual(peak_label("0630"), ("Peak", False))
        self.assertEqual(peak_label("0900"), ("Peak", False))
        self.assertEqual(peak_label("1600"), ("Non-Peak", False))
        self.assertEqual(peak_label("bad"), ("", True))

    def test_date_and_aor(self):
        self.assertEqual(normalize_date("1st July 2026"), "01/07/2026")
        self.assertEqual(build_aor("40", "1600")[0],
                         "[Year 2] [Cat A] 40 Seater Diesel Bus, 1-Way Trip, Up to 20km, Non-Peak")

    def test_money_has_dollar_sign_and_two_decimal_places(self):
        self.assertEqual(money("95"), "$95.00")
        self.assertEqual(money("S$ 1,234.5"), "$1234.50")

    def test_order_and_quotation_numbers_normalize_to_oa(self):
        self.assertEqual(normalize_oa_number("QN26/07/0449"), "OA26070449")
        self.assertEqual(normalize_oa_number("QT-26070312"), "OA26070312")
        self.assertEqual(normalize_oa_number("AT/CQ/2607/0189"), "OA26070189")
        self.assertEqual(extract_oa_number([page("Quotation # QN26/07/0449")]), "OA26070449")


class ParsersTest(unittest.TestCase):
    def test_leisure_two_rows(self):
        table = [
            ["No", "DATE", "TYPE", "TIME", "PICK-UP", "DROP-OFF", "QTY", "PRICE", "AMOUNT (S$)"],
            ["1", "01/07/2026", "40 SEATER", "0900", "Kranji Camp 3 Blk 605", "Sungei Gedong Camp", "1", "95", "95.00"],
            ["2", "01/07/2026", "40 SEATER", "1600", "Sungei Gedong Camp", "Kranji Camp 3 Blk 605", "1", "83", "83.00"],
        ]
        rows = parse_leisure_frontier([page("LEISURE FRONTIER", table)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["amount"], "$95.00")
        self.assertTrue(rows[0]["aor_title_line_item"].endswith("Peak"))
        self.assertTrue(rows[1]["aor_title_line_item"].endswith("Non-Peak"))

    def test_tong_tar_multiple_bus_review(self):
        table = [["Date", "Time", "Pick up", "Drop off", "Bus Type", "Unit Price"],
                 ["1st July 2026", "0800", "A", "B", "40-Seater Bus", "$155"]]
        rows = parse_tong_tar([page("TONG TAR 8 x 40-Seater", table)])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["needs_review"])
        self.assertEqual(rows[0]["amount"], "$155.00")

    def test_atlantic_verbatim_line_item(self):
        text = """ATLANTIC TRAVEL
PICKUP TIME: 1600
PICKUP POINT: Jurong Camp 2 Blk 218
DROPOFF POINT: Kranji Camp 3 Blk 605
POC: Alice 91234567
Line Item: [Year 2] [Cat A] 10 Seater Diesel Bus, 1-Way Trip, Up to 20km, Non-Peak
Unit Price: $55.00"""
        row = parse_atlantic([page(text)])[0]
        self.assertEqual(row["amount"], "$55.00")
        self.assertEqual(row["reporting_location"], "Jurong Camp 2 Blk 218")
        self.assertTrue(row["aor_title_line_item"].endswith("Non-Peak"))

    def test_ridewell_corrected_destination(self):
        table = [["S/N", "Date", "Time", "From", "To", "Way-Seater", "Qty", "Unit", "Total"],
                 ["1", "01/07/2026", "1000", "A", "Jurong Camp Singapore 123456\nKranji Camp Singapore 654321", "1w/10s", "1", "80", "80.00"]]
        row = parse_ridewell([page("RIDEWELL", table)])[0]
        self.assertTrue(row["needs_review"])
        self.assertIn("multiple", row["notes"])

    def test_jadia_invoice_only_and_po_override(self):
        text = """JADIA TAX INVOICE
ORDER NO: OA26003797
DATE: 01/07/2026
FROM: Alpha
TO: Bravo
TIME: 0800
TRANSPORT CHARGE: 250.00
ORDER NO: OA26003797
DATE: 02/07/2026
FROM: Charlie
TO: Delta
TIME: 1000
TRANSPORT CHARGE: 200.00"""
        rows = parse_jadia([page(text), PageData(2, "HANDWRITTEN DELIVERY ORDER", [], [])])
        self.assertEqual([row["amount"] for row in rows], ["$250.00", "$200.00"])
        self.assertEqual(rows[0]["aor_title_line_item"],
                         "5 Ton Lorry [With Driver] (Hourly Rental 0800-1800 Hrs of Next Day, Min 4 Hrs Charge) (1 Hr = 1 Job) (Normal/Urgent)")
        self.assertEqual(rows[1]["po_number"], "OA26003797")

    def test_external_fields_and_order(self):
        table = [["No", "DATE", "TYPE", "TIME", "PICK-UP", "DROP-OFF", "QTY", "PRICE", "AMOUNT"],
                 ["1", "1/7/2026", "40 SEATER", "0900", "A", "B", "1", "95", "95.00"]]
        rows = extract_rows([page("LEISURE FRONTIER", table)], "one.pdf", "x", "y", "26000001")
        self.assertEqual((rows[0]["need_by_date"], rows[0]["gr_date"], rows[0]["po_number"]), ("x", "y", "OA26000001"))
        self.assertFalse(rows[0]["needs_review"])

    def test_unreadable_image_only_pdf_has_explicit_review_note(self):
        rows = extract_rows([page("")], "scan.pdf", "x", "y", "OA1")
        self.assertTrue(rows[0]["needs_review"])
        self.assertIn("image-only", rows[0]["notes"])


class RealInvoiceIntegrationTest(unittest.TestCase):
    def test_image_only_ridewell_sample(self):
        sample = Path(__file__).parents[1] / "data" / "invoice_example.pdf"
        rows = extract_rows(read_pdf(sample.read_bytes()), sample.name, "01/08/2026", "02/08/2026", "OA123")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["po_number"], "OA26070449")
        self.assertEqual([row["amount"] for row in rows], ["$80.00", "$80.00"])
        self.assertEqual(rows[0]["reporting_location"],
                         "Kranji Camp 3 (Blk 605) (151 Choa Chu Kang Way Singapore 688248)")
        self.assertFalse(rows[0]["needs_review"])
        self.assertIn("Jurong Camp 1", rows[1]["to_location"])
        self.assertIn("Kranji Camp 3", rows[1]["to_location"])
        self.assertTrue(rows[1]["needs_review"])

    def _rows(self, filename, po="OA-INPUT"):
        sample = Path(__file__).parents[1] / "data" / filename
        return extract_rows(read_pdf(sample.read_bytes()), sample.name, "01/08/2026", "02/08/2026", po)

    def test_image_only_jadia_sample(self):
        rows = self._rows("invoice_example_2.pdf", po="")
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["amount"] for row in rows], ["$250.00", "$200.00"])
        self.assertEqual([row["po_number"] for row in rows], ["OA26003797", "OA26003797"])
        self.assertEqual(rows[0]["to_location"], "PIERCE AMMUNITION DEPOT")
        self.assertEqual(rows[1]["to_location"], "SINGAPORE EXPO")

    def test_image_only_tong_tar_sample(self):
        rows = self._rows("invoice_example_3.pdf")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount"], "$155.00")
        self.assertIn("40 Seater", rows[0]["aor_title_line_item"])
        self.assertTrue(rows[0]["needs_review"])

    def test_borderless_leisure_sample(self):
        rows = self._rows("invoice_example_4.pdf")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["po_number"], "OA26070312")
        self.assertEqual([row["amount"] for row in rows], ["$95.00", "$83.00"])
        self.assertEqual(rows[0]["to_location"], "Sungei Gedong Camp")
        self.assertEqual(rows[1]["to_location"], "Kranji Camp 3 Blk 605")

    def test_atlantic_without_searchable_masthead(self):
        rows = self._rows("invoice_example_5.pdf")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["po_number"], "OA26070189")
        self.assertEqual(rows[0]["vendor"], "Atlantic Travel")
        self.assertEqual(rows[0]["amount"], "$55.00")
        self.assertEqual(rows[0]["remarks"], "88066257 DARIUS")
        self.assertEqual(rows[0]["aor_title_line_item"],
                         "[Year 2] [Cat A] 10 Seater Diesel Bus, 1-Way Trip, Up to 20km, Non-Peak")


if __name__ == "__main__":
    unittest.main()
