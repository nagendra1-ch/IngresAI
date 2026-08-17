import os
import sys
import unittest

# Add backend root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.calculations import (
    absolute_difference,
    calculate_stage_of_extraction,
    convert_resource_unit,
    validate_depth,
    validate_stage,
    validate_rainfall,
    validate_resource_value
)
from app.utils.geography import (
    normalize_state,
    normalize_district,
    split_concatenated_geography
)
from app.services.gemini_service import GeminiService

class TestGroundwaterCalculations(unittest.TestCase):
    def test_absolute_difference(self):
        self.assertEqual(absolute_difference(10.5, 3.2), 7.3)
        self.assertEqual(absolute_difference(3.62, 3.61), 0.01)
        self.assertIsNone(absolute_difference(None, 5.0))
        self.assertIsNone(absolute_difference(12.0, None))

    def test_calculate_stage_of_extraction(self):
        # 19733.20 extraction / 68072.73 recharge * 100 = 28.99% (Kurnool dynamic dynamic calculations fallback)
        self.assertEqual(calculate_stage_of_extraction(68072.73, 19733.20), 28.99)
        self.assertEqual(calculate_stage_of_extraction(100.0, 0.0), 0.0)
        self.assertEqual(calculate_stage_of_extraction(0.0, 50.0), 0.0)
        self.assertIsNone(calculate_stage_of_extraction(None, 100.0))

    def test_convert_resource_unit(self):
        # BCM to HAM (1 BCM = 100,000 HAM)
        self.assertEqual(convert_resource_unit(0.6807, "BCM", "ham"), 68070.0)
        self.assertEqual(convert_resource_unit(1.0766, "bcm", "HAM"), 107660.0)
        # MCM to HAM (1 MCM = 100 HAM)
        self.assertEqual(convert_resource_unit(5.5, "MCM", "ham"), 550.0)
        self.assertIsNone(convert_resource_unit(None, "BCM", "ham"))

    def test_validators(self):
        self.assertTrue(validate_depth(3.61))
        self.assertTrue(validate_depth("5.5"))
        self.assertFalse(validate_depth("not_a_float"))
        self.assertTrue(validate_depth(None))

        self.assertTrue(validate_stage(30.51))
        self.assertTrue(validate_stage(120.0))  # overexploited is allowed but must be numeric

        self.assertTrue(validate_rainfall(1200.5))
        self.assertFalse(validate_rainfall(-10.0))
        
        self.assertTrue(validate_resource_value(0.0))
        self.assertFalse(validate_resource_value(-5.0))


class TestGeographyNormalization(unittest.TestCase):
    def test_normalize_state(self):
        self.assertEqual(normalize_state("andhra pradesh"), "Andhra Pradesh")
        self.assertEqual(normalize_state("ANDHRA   PRADESH"), "Andhra Pradesh")
        self.assertEqual(normalize_state("delhi"), "Delhi")

    def test_normalize_district(self):
        self.assertEqual(normalize_district("ANANTAPUR"), "Ananthapuramu")
        self.assertEqual(normalize_district("Ananthapuramu"), "Ananthapuramu")
        self.assertEqual(normalize_district("ysr"), "YSR Kadapa")
        self.assertEqual(normalize_district("YSR Kadapa"), "YSR Kadapa")
        self.assertEqual(normalize_district("Kurnool"), "Kurnool")
        self.assertEqual(normalize_district("kurnool"), "Kurnool")

    def test_split_concatenated_geography(self):
        # Splitting concatenated DistrictMandal strings
        d_clean, u_clean = split_concatenated_geography("Dr. B.R. Ambedkar KonaseemaAmalapuram")
        self.assertEqual(d_clean, "Dr. B.R. Ambedkar Konaseema")
        self.assertEqual(u_clean, "Amalapuram")

        d_clean, u_clean = split_concatenated_geography("Dr. B.R. Ambedkar Konaseemmalikipuram")
        self.assertEqual(d_clean, "Dr. B.R. Ambedkar Konaseema")
        self.assertEqual(u_clean, "Malikipuram")


class TestGeminiServiceInstructions(unittest.TestCase):
    def test_fallback_generator_same_period(self):
        verified_data = {
            "comparison": {
                "district_1": {
                    "district_name": "Kurnool",
                    "state_name": "Andhra Pradesh",
                    "depth_to_water_level_m_bgl": 3.61,
                    "rainfall_period": "January",
                    "observation_year": 2026,
                    "rainfall": {"value_mm": 650.0, "year": 2026, "period": "January–August"},
                    "resources": {
                        "annual_recharge_ham": 68072.73,
                        "annual_extractable_resource_ham": 64668.80,
                        "annual_extraction_ham": 19733.20,
                        "stage_of_extraction_percent": 30.51,
                        "net_groundwater_availability_ham": 41831.50
                    },
                    "assessment": {"year": 2025, "category": "Safe"},
                    "sources": {
                        "gwra": "GWRA_2025.pdf",
                        "groundwater_level": "January 2026.xlsx.pdf",
                        "rainfall": "IMD Gridded Rainfall Dataset"
                    }
                },
                "district_2": {
                    "district_name": "Ananthapuramu",
                    "state_name": "Andhra Pradesh",
                    "depth_to_water_level_m_bgl": 9.02,
                    "rainfall_period": "January",
                    "observation_year": 2026,
                    "rainfall": {"value_mm": 955.0, "year": 2026, "period": "January–August"},
                    "resources": {
                        "annual_recharge_ham": 126120.02,
                        "annual_extractable_resource_ham": 119813.93,
                        "annual_extraction_ham": 41819.10,
                        "stage_of_extraction_percent": 34.90,
                        "net_groundwater_availability_ham": 78907.83
                    },
                    "assessment": {"year": 2025, "category": "Safe"},
                    "sources": {
                        "gwra": "GWRA_2025.pdf",
                        "groundwater_level": "January 2026.xlsx.pdf",
                        "rainfall": "IMD Gridded Rainfall Dataset"
                    }
                }
            }
        }
        
        response = GeminiService._generate_fallback_response("Compare districts", verified_data)
        
        # Verify units
        self.assertIn("m bgl", response)
        self.assertIn("ham", response)
        # Verify title and headers
        self.assertIn("## Groundwater Comparison", response)
        self.assertIn("### Groundwater Depth", response)
        self.assertIn("### GWRA 2025 Comparison", response)
        # Verify exact mathematical calculations
        self.assertIn("5.41 m deeper", response)
        self.assertIn("percentage points", response)
        # Verify no caution star on same-period
        self.assertNotIn("Different periods*", response)
        
    def test_fallback_generator_different_period(self):
        verified_data = {
            "comparison": {
                "district_1": {
                    "district_name": "Kurnool",
                    "state_name": "Andhra Pradesh",
                    "depth_to_water_level_m_bgl": 3.61,
                    "rainfall_period": "August",
                    "observation_year": 2025,
                    "rainfall": {"value_mm": 650.0, "year": 2025, "period": "Annual"},
                    "resources": {
                        "annual_recharge_ham": 68072.73,
                        "annual_extractable_resource_ham": 64668.80,
                        "annual_extraction_ham": 19733.20,
                        "stage_of_extraction_percent": 30.51,
                        "net_groundwater_availability_ham": 41831.50
                    },
                    "assessment": {"year": 2025, "category": "Safe"},
                    "sources": {
                        "gwra": "GWRA_2025.pdf",
                        "groundwater_level": "August 2025.xlsx.pdf",
                        "rainfall": "IMD Gridded Rainfall Dataset"
                    }
                },
                "district_2": {
                    "district_name": "Ananthapuramu",
                    "state_name": "Andhra Pradesh",
                    "depth_to_water_level_m_bgl": 9.02,
                    "rainfall_period": "January",
                    "observation_year": 2026,
                    "rainfall": {"value_mm": 955.0, "year": 2026, "period": "January–August"},
                    "resources": {
                        "annual_recharge_ham": 126120.02,
                        "annual_extractable_resource_ham": 119813.93,
                        "annual_extraction_ham": 41819.10,
                        "stage_of_extraction_percent": 34.90,
                        "net_groundwater_availability_ham": 78907.83
                    },
                    "assessment": {"year": 2025, "category": "Safe"},
                    "sources": {
                        "gwra": "GWRA_2025.pdf",
                        "groundwater_level": "January 2026.xlsx.pdf",
                        "rainfall": "IMD Gridded Rainfall Dataset"
                    }
                }
            }
        }
        
        response = GeminiService._generate_fallback_response("Compare districts", verified_data)
        
        # Verify caution stars and warnings are present for different periods
        self.assertIn("Different periods*", response)
        self.assertIn("interpreted with caution", response)
        self.assertIn("different periods", response)

if __name__ == "__main__":
    unittest.main()
