"""Analysis and chart-selection tests.  NOT EXECUTED in the delivery task."""
from __future__ import annotations

import unittest

from analysis.selector import COLOR, select_charts


class AnalysisChartTests(unittest.TestCase):
    def test_missing_stress_does_not_generate_stress_chart(self):
        case = {
            "case_id": 0,
            "crack_available": True,
            "series": {
                "cycle": [1, 2],
                "mechanical_time_total": [0.0, 0.1],
                "ball_count": [10, 10],
                "frame_displacement_mean_m": [0.0, 0.1],
                "crack_count_cumulative": [0, 0],
            },
            "histograms": {},
            "orientation": {"status": "NOT_CAPTURED"},
            "spatial_density": {"status": "NOT_GENERATED"},
            "correlation": {"status": "NOT_GENERATED"},
        }
        charts = select_charts([case], {"status": "NOT_GENERATED"})
        self.assertFalse(any("stress" in item["id"] for item in charts))
        self.assertTrue(any(item["type"] == "dual-line" for item in charts))

    def test_color_semantics_are_stable(self):
        self.assertEqual(COLOR["primary"], "#3C5488")
        self.assertEqual(COLOR["fracture"], "#E64B35")
        self.assertEqual(COLOR["low"], "#EAEEF5")

    def test_multi_case_chart_uses_native_summaries(self):
        case_a = {
            "case_id": 0,
            "series": {},
            "histograms": {},
            "orientation": {},
            "spatial_density": {},
            "correlation": {},
        }
        comparison = {
            "status": "GENERATED",
            "cases": [
                {"case_id": 0, "stress_max_pa": 1e6, "crack_final": 2},
                {"case_id": 1, "stress_max_pa": 2e6, "crack_final": 4},
            ],
        }
        charts = select_charts([case_a], comparison)
        compare = [item for item in charts if item["type"] == "case-compare"]
        self.assertTrue(compare)
        self.assertIn("no time interpolation", compare[0]["basis"])


if __name__ == "__main__":
    unittest.main()
