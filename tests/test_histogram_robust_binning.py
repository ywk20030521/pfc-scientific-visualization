"""A5 robust histogram binning tests."""
from __future__ import annotations

import unittest

import numpy as np

from analysis.engine import _histogram
from analysis.intelligence import select_chart_decisions


class RobustHistogramTests(unittest.TestCase):
    def test_robust_bins_preserve_every_finite_observation(self):
        values = np.asarray(
            [index * 1.0e-6 for index in range(100)]
            + [0.025, 0.0496, np.nan],
            dtype=np.float64,
        )
        histogram = _histogram(values, bins=32)
        self.assertEqual(histogram["status"], "GENERATED")
        self.assertEqual(histogram["range_policy"], "ROBUST_P05_P95_WITH_OVERFLOW")
        self.assertEqual(histogram["total_count"], len(values))
        self.assertEqual(histogram["finite_count"], 102)
        self.assertEqual(histogram["missing_count"], 1)
        self.assertEqual(sum(histogram["counts"]), histogram["finite_count"])
        self.assertEqual(histogram["counts"][0], histogram["underflow_count"])
        self.assertEqual(histogram["counts"][-1], histogram["overflow_count"])
        self.assertGreater(histogram["overflow_count"], 0)
        self.assertEqual(
            histogram["labels"][0],
            "< P05",
        )
        self.assertEqual(
            histogram["labels"][-1],
            "> P95",
        )
        self.assertEqual(len(histogram["labels"]), len(histogram["counts"]))
        self.assertEqual(len(histogram["bins"]), len(histogram["counts"]))

    def test_extreme_case_does_not_collapse_all_values_into_one_bin(self):
        values = np.asarray(
            [0.000001 * (index + 1) for index in range(1000)]
            + [0.025],
            dtype=np.float64,
        )
        histogram = _histogram(values, bins=32)
        nonempty_interior = [
            item["count"]
            for item in histogram["bins"]
            if item["kind"] == "INTERIOR" and item["count"] > 0
        ]
        self.assertGreater(len(nonempty_interior), 5)
        self.assertGreater(histogram["overflow_count"], 0)
        self.assertLessEqual(
            histogram["overflow_count"],
            histogram["finite_count"] * 0.05,
        )
        self.assertEqual(sum(histogram["counts"]), len(values))
        self.assertGreater(histogram["interior_min"], 0.0)
        self.assertGreater(
            histogram["observed_max"],
            histogram["interior_max"],
        )

    def test_chart_spec_exposes_overflow_semantics_and_missing_count(self):
        values = np.asarray(
            [index * 1.0e-6 for index in range(100)]
            + [0.05, np.nan],
            dtype=np.float64,
        )
        case = {
            "status": "GENERATED",
            "case_id": 0,
            "crack_available": False,
            "series": {},
            "histograms": {"final_displacement_m": _histogram(values)},
            "orientation": {"status": "NOT_CAPTURED"},
            "spatial_density": {"status": "NOT_GENERATED"},
            "correlation": {"status": "NOT_GENERATED"},
        }
        result = select_chart_decisions(
            [case],
            {"status": "NOT_GENERATED", "reason": "One Case"},
        )
        chart = next(
            item for item in result["charts"]
            if item["id"] == "case_0:displacement_hist"
        )
        self.assertEqual(
            chart["range_policy"],
            "ROBUST_P05_P95_WITH_OVERFLOW",
        )
        self.assertEqual(chart["finite_count"], 101)
        self.assertEqual(chart["missing_count"], 1)
        self.assertEqual(chart["decision"]["missing_count"], 1)
        self.assertEqual(chart["bin_labels"][0], "< P05")
        self.assertEqual(chart["bin_labels"][-1], "> P95")
        self.assertEqual(sum(chart["counts"]), chart["finite_count"])


if __name__ == "__main__":
    unittest.main()
