"""PR3 Chart Intelligence tests. NOT EXECUTED in delivery."""
from __future__ import annotations

import unittest

from analysis.intelligence import channel_features, select_chart_decisions


def _case() -> dict:
    return {
        "status": "GENERATED",
        "case_id": 0,
        "crack_available": False,
        "series": {
            "cycle": [1, 2, 3, 4],
            "mechanical_time_total": [0.0, 0.1, 0.2, 0.3],
            "frame_displacement_mean_m": [0.0, 0.002, 0.004, 0.007],
            "frame_speed_mean_m_s": [None, 0.01, 0.02, 0.03],
            "axial_strain": [0.0, 0.01, 0.02, 0.03],
            "axial_stress_pa": [0.0, 1.2e6, 2.5e6, 4.1e6],
            "axial_load_per_unit_thickness_n_m": [
                0.0,
                1.2e4,
                2.5e4,
                4.1e4,
            ],
        },
        "histograms": {"final_displacement_m": {"status": "NOT_CAPTURED"}},
        "orientation": {"status": "NOT_CAPTURED"},
        "spatial_density": {"status": "NOT_GENERATED"},
        "correlation": {"status": "NOT_GENERATED"},
    }


class ChartIntelligenceTests(unittest.TestCase):
    def test_each_selected_chart_has_a_transparent_reason(self):
        result = select_chart_decisions(
            [_case()],
            {"status": "NOT_GENERATED", "reason": "One Case"},
        )
        self.assertTrue(result["charts"])
        for chart in result["charts"]:
            self.assertTrue(chart["source_channels"])
            self.assertTrue(chart["decision"]["reason"])
            self.assertIn("alternatives", chart["decision"])
            self.assertGreaterEqual(chart["decision"]["missing_count"], 0)

    def test_missing_stress_is_rejected_not_zero_filled(self):
        case = _case()
        case["series"].pop("axial_stress_pa")
        result = select_chart_decisions(
            [case],
            {"status": "NOT_GENERATED", "reason": "One Case"},
        )
        self.assertFalse(any("stress_strain" in item["id"] for item in result["charts"]))
        rejected = {item["id"]: item for item in result["rejected"]}
        self.assertEqual(rejected["case_0:stress_strain"]["status"], "NOT_CAPTURED")

    def test_manual_override_is_constrained_by_data_shape(self):
        result = select_chart_decisions(
            [_case()],
            {"status": "NOT_GENERATED", "reason": "One Case"},
            overrides={"charts": {"case_0:stress_strain": {"type": "scatter"}}},
        )
        stress = next(item for item in result["charts"] if item["id"] == "case_0:stress_strain")
        self.assertEqual(stress["type"], "scatter")
        self.assertEqual(stress["decision"]["manual_override"]["status"], "APPLIED")

    def test_incompatible_manual_override_is_rejected(self):
        result = select_chart_decisions(
            [_case()],
            {"status": "NOT_GENERATED", "reason": "One Case"},
            overrides={"charts": {"case_0:stress_strain": {"type": "histogram"}}},
        )
        stress = next(item for item in result["charts"] if item["id"] == "case_0:stress_strain")
        self.assertEqual(stress["type"], "line")
        self.assertEqual(stress["decision"]["manual_override"]["status"], "REJECTED")

    def test_channel_feature_reports_missing_and_constant(self):
        features = channel_features([1.0, None, 1.0, 1.0])
        self.assertEqual(features["missing_count"], 1)
        self.assertTrue(features["constant"])
        self.assertEqual(features["count"], 3)

    def test_constant_stress_is_rejected(self):
        case = _case()
        case["series"]["axial_stress_pa"] = [0.0] * 4
        case["series"]["axial_strain"] = [0.0] * 4
        result = select_chart_decisions(
            [case],
            {"status": "NOT_GENERATED", "reason": "One Case"},
        )
        self.assertFalse(any("stress" in item["id"] for item in result["charts"]))
        rejected = {item["id"]: item for item in result["rejected"]}
        self.assertEqual(rejected["case_0:stress_strain"]["status"], "NOT_GENERATED")
        self.assertIn("constant", rejected["case_0:stress_strain"]["reason"])


if __name__ == "__main__":
    unittest.main()
