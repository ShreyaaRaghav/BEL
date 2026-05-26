import unittest
from unittest.mock import patch
from app.ai_engine.evaluator import evaluate_pass_fail
from app.ai_engine.pdf_parser import parse_pdf

class TestChecksheetParserAndEvaluator(unittest.TestCase):

    def test_evaluator_numeric_range(self):
        # Range field: min=4.95, max=5.05
        field = {"type": "numeric", "range_type": "range", "min": 4.95, "max": 5.05, "conditions": None}
        self.assertEqual(evaluate_pass_fail(field, "5.00"), "PASS")
        self.assertEqual(evaluate_pass_fail(field, "4.95"), "PASS")
        self.assertEqual(evaluate_pass_fail(field, "5.05"), "PASS")
        self.assertEqual(evaluate_pass_fail(field, "4.90"), "FAIL")
        self.assertEqual(evaluate_pass_fail(field, "5.10"), "FAIL")
        self.assertEqual(evaluate_pass_fail(field, "invalid"), "INVALID")
        self.assertEqual(evaluate_pass_fail(field, ""), "PENDING")
        self.assertEqual(evaluate_pass_fail(field, None), "PENDING")

    def test_evaluator_numeric_min_only(self):
        # min_only: >= 3.0
        field = {"type": "numeric", "range_type": "min_only", "min": 3.0, "max": None, "conditions": None}
        self.assertEqual(evaluate_pass_fail(field, "3.0"), "PASS")
        self.assertEqual(evaluate_pass_fail(field, "4.5"), "PASS")
        self.assertEqual(evaluate_pass_fail(field, "2.9"), "FAIL")

    def test_evaluator_numeric_max_only(self):
        # max_only: <= 10.0
        field = {"type": "numeric", "range_type": "max_only", "min": None, "max": 10.0, "conditions": None}
        self.assertEqual(evaluate_pass_fail(field, "10.0"), "PASS")
        self.assertEqual(evaluate_pass_fail(field, "5.0"), "PASS")
        self.assertEqual(evaluate_pass_fail(field, "10.1"), "FAIL")

    def test_evaluator_numeric_exact(self):
        # exact: == 0.0
        field = {"type": "numeric", "range_type": "exact", "min": 0.0, "max": 0.0, "conditions": None}
        self.assertEqual(evaluate_pass_fail(field, "0.0"), "PASS")
        self.assertEqual(evaluate_pass_fail(field, "0"), "PASS")
        self.assertEqual(evaluate_pass_fail(field, "0.1"), "FAIL")

    def test_evaluator_categorical(self):
        # Categorical: clean, intact
        field = {"type": "categorical", "range_type": "unknown", "min": None, "max": None, "conditions": ["clean", "intact"]}
        self.assertEqual(evaluate_pass_fail(field, "clean and intact"), "PASS")
        self.assertEqual(evaluate_pass_fail(field, "Clean & Intact"), "PASS")
        self.assertEqual(evaluate_pass_fail(field, "clean"), "FAIL")  # missing intact
        self.assertEqual(evaluate_pass_fail(field, "dirty intact"), "FAIL") # missing clean

    @patch("app.services.pdf_service.extract_text_from_pdf")
    @patch("app.ai_engine.ai_parser.parse_with_ai")
    def test_pdf_parser_ai_path(self, mock_parse_with_ai, mock_extract_text):
        # Mock PDF text extraction and AI parsing success
        mock_extract_text.return_value = "Mocked PDF checksheet text"
        expected_fields = [
            {"title": "Test AI Parameter", "type": "numeric", "unit": "V", "min": 1.0, "max": 2.0, "range_type": "range", "conditions": None}
        ]
        mock_parse_with_ai.return_value = expected_fields

        # Call parser with a dummy path
        fields = parse_pdf("dummy_checksheet.pdf")
        self.assertEqual(fields, expected_fields)
        mock_parse_with_ai.assert_called_once()
        mock_extract_text.assert_called_once_with("dummy_checksheet.pdf")

    @patch("app.services.pdf_service.extract_text_from_pdf")
    @patch("app.ai_engine.ai_parser.parse_with_ai")
    def test_pdf_parser_fallback_path(self, mock_parse_with_ai, mock_extract_text):
        # Mock PDF text extraction and AI parsing failure to trigger rule-based fallback
        mock_extract_text.return_value = "01 Baseline Voltage Stability ___________ V 4.95V - 5.05V [ ] Pass"
        mock_parse_with_ai.return_value = None

        # Call parser with a dummy path
        fields = parse_pdf("dummy_checksheet.pdf")
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]["title"], "Baseline Voltage Stability")
        self.assertEqual(fields[0]["min"], 4.95)
        self.assertEqual(fields[0]["max"], 5.05)
        self.assertEqual(fields[0]["unit"], "V")
        mock_parse_with_ai.assert_called_once()
        mock_extract_text.assert_called_once_with("dummy_checksheet.pdf")

if __name__ == "__main__":
    unittest.main()
