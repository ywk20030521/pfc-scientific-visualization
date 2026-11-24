"""A13 data-driven chart-selection contract tests."""
from __future__ import annotations

import unittest

from analysis.intelligence import select_chart_decisions


REQUIRED_FIELDS = {
    "chart_id",
    "chart_type",
    "case_id",
    "source_variables",
    "source_data",
    "physical_meaning",
    "unit",
    "selection_reason",
    "omission_reason",
    "data_quality",
    "publication_priority",
}


def _case() -> dict:
    return {
        "status": "GENERATED",
        "case_id": 0,
        "dimension": 2,
        "crack_available": False,
        "series": {
            "cycle": [1, 2, 3, 4],
            "mechanical_time_total": [0.0, 0.1, 0.2, 0.3],
            "frame_displacement_mean_m": [0.0, 0.002, 0.004, 0.007],
            "frame_speed_mean_m_s": [None, 0.01, 0.02, 0.03],
            "frame_acceleration_mean_m_s2": [None, 0.2, 0.3, 0.4],
            "axial_strain": [0.0, 0.01, 0.02, 0.03],
            "axial_stress_pa": [0.0, 1.2e6, 2.5e6, 4.1e6],
            "axial_load_per_unit_thickness_n_m": [0.0, 1.2e4, 2.5e4, 4.1e4],
        },
        "histograms": {"final_displacement_m": {"status": "NOT_CAPTURED"}},
        "orientation": {"status": "NOT_CAPTURED"},
        "spatial_density": {"status": "NOT_GENERATED"},
        "correlation": {"status": "NOT_GENERATED"},
    }


class ChartSelectionContractTests(unittest.TestCase):
    def test_every_selected_and_omitted_candidate_has_the_contract(self):
        result = select_chart_decisions(
            [_case()],
            {"status": "NOT_GENERATED", "reason": "One Case"},
        )
        self.assertTrue(result["charts"])
        self.assertTrue(result["rejected"])
        for item in result["charts"]:
            self.assertTrue(REQUIRED_FIELDS.issubset(item), item["id"])
            self.assertTrue(item["selection_reason"])
            self.assertIsNone(item["omission_reason"])
        for item in result["rejected"]:
            self.assertTrue(REQUIRED_FIELDS.issubset(item), item["id"])
            self.assertIsNone(item["selection_reason"])
            self.assertTrue(item["omission_reason"])
            self.assertEqual(item["publication_priority"], "EXCLUDED")

    def test_unsupported_families_are_recorded_with_explicit_reasons(self):
        result = select_chart_decisions(
            [_case()],
            {"status": "NOT_GENERATED", "reason": "One Case"},
        )
        rejected = {item["id"]: item for item in result["rejected"]}
        expected = {
            "case_0:motion_cracks",
            "case_0:fracture_rose",
            "case_0:displacement_hist",
            "case_0:particle_density",
            "case_0:correlation",
        }
        self.assertTrue(expected.issubset(rejected))
        for chart_id in expected:
            self.assertTrue(rejected[chart_id]["omission_reason"])
            self.assertFalse(
                rejected[chart_id]["data_quality"]["missing_values_treated_as_zero"]
            )

    def test_constant_channel_is_omitted_instead_of_forced(self):
        case = _case()
        case["series"]["frame_speed_mean_m_s"] = [0.01] * 4
        result = select_chart_decisions(
            [case],
            {"status": "NOT_GENERATED", "reason": "One Case"},
        )
        rejected = {item["id"]: item for item in result["rejected"]}
        self.assertNotIn(
            "case_0:speed_time",
            {item["id"] for item in result["charts"]},
        )
        self.assertTrue(
            rejected["case_0:speed_time"]["data_quality"][
                "constant_channel_rejected"
            ]
        )


if __name__ == "__main__":
    unittest.main()
