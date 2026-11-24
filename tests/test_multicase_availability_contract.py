"""A8 multi-Case availability, missing-value and color-contract tests."""
from __future__ import annotations

import unittest

from analysis.engine import _case_comparison
from analysis.intelligence import select_chart_decisions


def _analysis_case(
    case_id: int,
    *,
    stress: float | None,
    displacement: float | None,
    crack_final: int | None,
) -> dict:
    return {
        "case_id": case_id,
        "crack_available": crack_final is not None,
        "statistics": {
            "axial_stress_pa": (
                {"status": "GENERATED", "max": stress}
                if stress is not None
                else {"status": "NOT_CAPTURED"}
            ),
            "axial_strain": {"status": "NOT_CAPTURED"},
            "displacement_m": (
                {"status": "GENERATED", "mean": displacement}
                if displacement is not None
                else {"status": "NOT_CAPTURED"}
            ),
        },
        "series": {
            "crack_count_cumulative": (
                [0, crack_final] if crack_final is not None else []
            )
        },
    }


class MultiCaseAvailabilityTests(unittest.TestCase):
    def test_engine_counts_missing_cases_and_reasons_without_zero_fill(self):
        comparison = _case_comparison(
            [
                _analysis_case(0, stress=None, displacement=1.0e-3, crack_final=None),
                _analysis_case(1, stress=1.0e6, displacement=2.0e-3, crack_final=None),
                _analysis_case(2, stress=2.0e6, displacement=None, crack_final=None),
                _analysis_case(3, stress=None, displacement=4.0e-3, crack_final=None),
            ]
        )
        stress = comparison["metrics"]["stress_max_pa"]
        self.assertEqual(stress["status"], "GENERATED")
        self.assertEqual(stress["total_case_count"], 4)
        self.assertEqual(stress["available_case_count"], 2)
        self.assertEqual(stress["missing_case_count"], 2)
        self.assertEqual(stress["missing_case_ids"], [0, 3])
        self.assertEqual(
            [item["value"] for item in stress["cases"]],
            [None, 1.0e6, 2.0e6, None],
        )
        self.assertEqual(
            stress["cases"][0]["reason"],
            "sample.axial_stress:NOT_CAPTURED",
        )
        self.assertIsNone(comparison["cases"][0]["stress_max_pa"])

        displacement = comparison["metrics"]["displacement_mean_m"]
        self.assertEqual(displacement["available_case_count"], 3)
        self.assertEqual(displacement["missing_case_ids"], [2])

        cracks = comparison["metrics"]["crack_final"]
        self.assertEqual(cracks["status"], "NOT_CAPTURED")
        self.assertEqual(cracks["available_case_count"], 0)
        self.assertEqual(cracks["missing_case_ids"], [0, 1, 2, 3])

    def test_chart_consumes_explicit_counts_and_uses_one_metric_color(self):
        comparison = _case_comparison(
            [
                _analysis_case(0, stress=None, displacement=1.0e-3, crack_final=None),
                _analysis_case(1, stress=1.0e6, displacement=2.0e-3, crack_final=None),
                _analysis_case(2, stress=2.0e6, displacement=None, crack_final=None),
                _analysis_case(3, stress=None, displacement=4.0e-3, crack_final=None),
            ]
        )
        charts = select_chart_decisions(
            [],
            comparison,
        )["charts"]
        stress = next(
            chart
            for chart in charts
            if chart["id"] == "experiment:case_comparison:stress_max_pa"
        )
        self.assertEqual(stress["missing_case_count"], 2)
        self.assertEqual(stress["missing_case_ids"], [0, 3])
        self.assertEqual(stress["available_case_count"], 2)
        self.assertEqual(stress["total_case_count"], 4)
        self.assertEqual(stress["decision"]["missing_count"], 2)
        self.assertEqual(
            stress["decision"]["availability"]["missing_case_ids"],
            [0, 3],
        )
        self.assertEqual(stress["color"], "#3C5488")
        self.assertEqual(
            stress["color_policy"],
            "SINGLE_COLOR_BY_METRIC_SEMANTICS",
        )
        self.assertNotIn("colors", stress)
        self.assertEqual(
            [row.get("stress_max_pa") for row in stress["data"]],
            [None, 1.0e6, 2.0e6, None],
        )

    def test_inconsistent_availability_contract_is_rejected(self):
        comparison = _case_comparison(
            [
                _analysis_case(0, stress=1.0e6, displacement=1.0, crack_final=None),
                _analysis_case(1, stress=2.0e6, displacement=2.0, crack_final=None),
            ]
        )
        comparison["metrics"]["stress_max_pa"]["missing_case_count"] = 9
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            select_chart_decisions([], comparison)


if __name__ == "__main__":
    unittest.main()
