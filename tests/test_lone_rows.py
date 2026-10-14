"""The lone_rows lever: a table row the same as its header (a one-row table) sent once, not as its own header too."""
import stubs  # noqa: F401 (a clean environment)
import unittest

from semantic_pdf_diff.settings import Settings

class LoneRows(unittest.TestCase):
    def test_a_row_that_is_its_own_header_is_sent_once(self):
        row = ["AC Rating", "6.4 kW"]
        self.assertEqual(Settings(lone_rows=True).row_text(row, list(row)), 'Row: ["AC Rating", "6.4 kW"]')
        self.assertEqual(Settings().row_text(row, list(row)),
                         'Header: ["AC Rating", "6.4 kW"]\nRow: ["AC Rating", "6.4 kW"]')

    def test_a_row_under_another_header_keeps_it(self):
        head, row = ["Item", "Power"], ["Pump P-1", "10 kW"]
        self.assertEqual(Settings(lone_rows=True).row_text(head, row), Settings().row_text(head, row))

if __name__ == "__main__":
    unittest.main()
