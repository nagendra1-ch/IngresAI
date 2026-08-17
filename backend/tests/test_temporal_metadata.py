import unittest
from app.utils.temporal import normalize_period_with_year, validate_and_normalize_metadata

class TestTemporalMetadata(unittest.TestCase):
    
    def test_normalization_no_duplicate_years(self):
        # Case: period already contains the year
        self.assertEqual(normalize_period_with_year("January 2026", 2026), "January 2026")
        self.assertEqual(normalize_period_with_year("January–August 2026", 2026), "January–August 2026")
        self.assertEqual(normalize_period_with_year("Annual 2025", 2025), "Annual 2025")
        
        # Case: period does not contain the year
        self.assertEqual(normalize_period_with_year("January", 2026), "January 2026")
        self.assertEqual(normalize_period_with_year("February", 2026), "February 2026")
        self.assertEqual(normalize_period_with_year("August", 2026), "August 2026")
        self.assertEqual(normalize_period_with_year("Pre-Monsoon", 2025), "Pre-Monsoon 2025")
        self.assertEqual(normalize_period_with_year("Post-Monsoon", 2025), "Post-Monsoon 2025")
        
    def test_validate_and_normalize_metadata_from_source(self):
        # Case: January 2026 source file
        self.assertEqual(
            validate_and_normalize_metadata("January 2026.xlsx.pdf", "January", 2026),
            "January 2026"
        )
        # Case: February 2026 source file
        self.assertEqual(
            validate_and_normalize_metadata("February 2026.xlsx.pdf", "February", 2026),
            "February 2026"
        )
        # Case: August 2026 source file
        self.assertEqual(
            validate_and_normalize_metadata("August 2026.xlsx.pdf", "August", 2026),
            "August 2026"
        )
        # Case: Pre-Monsoon 2025 source file
        self.assertEqual(
            validate_and_normalize_metadata("Pre-Monsoon 2025.xlsx.pdf", "Pre-Monsoon", 2025),
            "Pre-Monsoon 2025"
        )
        # Case: Post-Monsoon 2025 source file
        self.assertEqual(
            validate_and_normalize_metadata("Post-Monsoon 2025.xlsx.pdf", "Post-Monsoon", 2025),
            "Post-Monsoon 2025"
        )
        
    def test_no_monthly_to_annual_conversion(self):
        # Monthly data should retain its specific period and not be converted to annual
        res = validate_and_normalize_metadata("January 2026.xlsx.pdf", "January", 2026)
        self.assertNotIn("Annual", res)
        self.assertEqual(res, "January 2026")
        
if __name__ == "__main__":
    unittest.main()
