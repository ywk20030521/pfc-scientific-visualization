"""A6 axis notation, zero policy and chart-contract tests."""
from __future__ import annotations

import unittest

from analysis.formatting import formatting_spec
from analysis.intelligence import select_chart_decisions


def _case() -> dict:
    return {
        "status": "GENERATED",
        "case_id": 0,
        "crack_available": False,
        "series": {
            "cycle": [1, 2, 3, 4],
            "mechanical_time_total": [0.1, 0.2, 0.3, 0.4],
            "frame_displacement_mean_m": [0.0, 0.0002, 0.0004, 0.0007],
            "frame_speed_mean_m_s": [None, 0.012, 0.017, 0.021],
            "frame_acceleration_mean_m_s2": [None, 40.0, 65.0, 52.0],
            "crack_count_cumulative": [0, 0, 0, 0],
        },
        "histograms": {"final_displacement_m": {"status": "NOT_CAPTURED"}},
        "orientation": {"status": "NOT_CAPTURED"},
        "spatial_density": {"status": "NOT_GENERATED"},
        "correlation": {"status": "NOT_GENERATED"},
    }


class AxisContractTests(unittest.TestCase):
    def test_scientific_notation_uses_one_axis_exponent(self):
        formatting = formatting_spec(
            "m",
            [0.0, 1.0e-4, 3.5e-4, 7.0e-4],
            significant_digits=4,
        )
        self.assertTrue(formatting["scientific"])
        self.assertEqual(
            formatting["axis_notation"],
            "SCIENTIFIC_SHARED_EXPONENT",
        )
        self.assertEqual(formatting["axis_exponent"], -4)
        self.assertAlmostEqual(formatting["axis_scale"], 1.0e-4)
        self.assertEqual(formatting["axis_scale_label"], "× 10⁻⁴")
        self.assertEqual(formatting["decimals"], 3)

    def test_line_axis_avoid_zero_while_area_axis_keeps_zero(self):
        result = select_chart_decisions(
            [_case()],
            {"status": "NOT_GENERATED", "reason": "One Case"},
        )
        speed = next(
            chart for chart in result["charts"]
            if chart["id"] == "case_0:speed_time"
        )
        motion = next(
            chart for chart in result["charts"]
            if chart["id"] == "case_0:motion"
        )
        self.assertFalse(speed["axis_contract"]["x"]["include_zero"])
        self.assertFalse(speed["axis_contract"]["y"]["include_zero"])
        self.assertEqual(
            speed["axis_contract"]["y"]["range_policy"],
            "DATA_EXTENT_PADDED",
        )
        self.assertTrue(motion["axis_contract"]["y"]["include_zero"])
        self.assertEqual(
            motion["axis_contract"]["y"]["range_policy"],
            "ZERO_INCLUDED",
        )
        self.assertEqual(
            motion["axis_contract"]["y"]["axis_exponent"],
            -4,
        )
        self.assertEqual(
            motion["axis_contract"]["y"]["axis_scale_label"],
            "× 10⁻⁴",
        )

    def test_case_comparison_axis_is_zero_based(self):
        comparison = {
            "status": "GENERATED",
            "cases": [
                {"case_id": 0, "displacement_mean_m": 0.1},
                {"case_id": 1, "displacement_mean_m": 0.2},
            ],
            "metrics": {
                "displacement_mean_m": {
                    "status": "GENERATED",
                    "unit": "m",
                    "source_channel": "ball.displacement",
                    "total_case_count": 2,
                    "available_case_count": 2,
                    "missing_case_count": 0,
                    "missing_case_ids": [],
                    "comparable": True,
                    "not_comparable_reason": None,
                    "cases": [
                        {"case_id": 0, "value": 0.1, "state": "AVAILABLE", "reason": None},
                        {"case_id": 1, "value": 0.2, "state": "AVAILABLE", "reason": None},
                    ],
                }
            },
        }
        result = select_chart_decisions([], comparison)
        chart = next(
            item for item in result["charts"]
            if item["id"] == "experiment:case_comparison:displacement_mean_m"
        )
        self.assertTrue(chart["axis_contract"]["y"]["include_zero"])
        self.assertEqual(
            chart["axis_contract"]["y"]["range_policy"],
            "ZERO_INCLUDED",
        )


if __name__ == "__main__":
    unittest.main()
