"""A9 legacy temporal chart compatibility tests."""
from __future__ import annotations

import unittest

from viewer.payload_builder import PayloadBuildError, _selected_indices, _slice_chart


class LegacyArtifactCompatibilityTests(unittest.TestCase):
    def test_full_extent_legacy_temporal_chart_is_sliced_and_marked(self):
        chart = {
            "case_id": 0,
            "type": "line",
            "x": {"name": "Cycle", "unit": "cycle", "data": list(range(351))},
            "y": {"name": "speed", "unit": "m/s", "data": list(range(351))},
        }
        selected = _selected_indices(351, 8)
        result = _slice_chart(chart, selected, 351)
        self.assertEqual(result["source_indices"], selected)
        self.assertEqual(len(result["x"]["data"]), 8)
        self.assertEqual(len(result["y"]["data"]), 8)
        self.assertEqual(
            result["compatibility"]["source_indices"],
            "LEGACY_EXACT_FULL_SOURCE_EXTENT",
        )

    def test_ambiguous_legacy_temporal_chart_is_rejected(self):
        chart = {
            "case_id": 0,
            "type": "line",
            "x": {"name": "Cycle", "unit": "cycle", "data": list(range(351))},
            "y": {"name": "speed", "unit": "m/s", "data": list(range(350))},
        }
        with self.assertRaisesRegex(PayloadBuildError, "source_indices"):
            _slice_chart(chart, _selected_indices(351, 8), 351)

    def test_non_temporal_legacy_artifact_does_not_require_source_indices(self):
        chart = {
            "case_id": 0,
            "type": "heatmap",
            "x": [0.0, 1.0],
            "y": [0.0, 1.0],
            "z": [[1, 2], [3, 4]],
        }
        result = _slice_chart(chart, [0, 1], 2)
        self.assertEqual(
            result["compatibility"]["source_indices"],
            "NOT_REQUIRED_NON_TEMPORAL_CHART",
        )


if __name__ == "__main__":
    unittest.main()
