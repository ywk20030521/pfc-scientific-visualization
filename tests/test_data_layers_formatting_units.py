"""PR1-PR2 data-layer, formatting and unit tests. NOT EXECUTED in delivery."""
from __future__ import annotations

import unittest

from analysis.formatting import format_display_series, format_number
from analysis.units import conversion_factor, convert_values
from schema import (
    make_analysis_data_layer,
    make_display_data_layer,
)


class DataLayerFormattingTests(unittest.TestCase):
    def test_external_standardized_parent_and_local_lineage_are_explicit(self):
        external_parent = "pfc-headless:delivery-sha256:case_0"
        analysis = make_analysis_data_layer(
            0,
            [{"path": "case_0/analysis.npz", "sha256": "b" * 64}],
            parent_layer_id=external_parent,
            operations=[
                {
                    "method": "x(t)-x(0)",
                    "outputs": ["ball.displacement"],
                }
            ],
        )
        display = make_display_data_layer(
            0,
            [{"path": "chart_specs.json", "sha256": "c" * 64}],
            parent_layer_ids=[analysis["layer_id"]],
            formatting={"method": "DISPLAY_ONLY"},
        )
        self.assertEqual(analysis["parent_layers"], [external_parent])
        self.assertIn(analysis["layer_id"], display["parent_layers"])
        self.assertEqual(display["layer"], "DISPLAY_DATA")

    def test_display_requires_a_declared_formatting_method(self):
        with self.assertRaises(ValueError):
            make_display_data_layer(
                0,
                [],
                parent_layer_ids=["analysis_data:case_0"],
                formatting={},
            )

    def test_tiny_value_uses_scientific_display(self):
        self.assertEqual(
            format_number(0.000000123456789, significant_digits=4),
            "1.235 × 10⁻⁷",
        )

    def test_display_does_not_mutate_analysis_values(self):
        source = [1.23456789, None, 0.000012345]
        before = list(source)
        display = format_display_series(source, unit="m")
        self.assertEqual(source, before)
        self.assertEqual(display["values"][1], "—")
        self.assertGreaterEqual(display["formatting"]["tooltip_digits"], 6)

    def test_unit_conversion_preserves_missing_values(self):
        converted, record = convert_values([1.0, None, 2.0], "MPa", "Pa")
        self.assertEqual(converted, [1.0e6, None, 2.0e6])
        self.assertEqual(record["source_unit"], "MPa")
        self.assertEqual(record["target_unit"], "Pa")
        self.assertTrue(record["preserves_missing_values"])

    def test_incompatible_units_are_rejected(self):
        with self.assertRaises(ValueError):
            conversion_factor("m", "s")


if __name__ == "__main__":
    unittest.main()
