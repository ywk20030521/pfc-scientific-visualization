"""PR5 adaptive figure-composition tests. NOT EXECUTED in delivery."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from charts.publication import (
    compose_publication_svg,
    layout_panels,
    write_figure_plan,
    write_publication_plan,
)


class PublicationCompositionTests(unittest.TestCase):
    def test_odd_and_even_counts_have_no_placeholder_panels(self):
        for count in (2, 3, 4, 5, 6, 7, 8, 10):
            with self.subTest(count=count):
                layout = layout_panels(count)
                self.assertEqual(len(layout["panels"]), count)
                self.assertEqual(layout["empty_placeholder_panels"], 0)
                for rectangle in layout["panels"]:
                    self.assertGreater(rectangle["width"], 0)
                    self.assertGreater(rectangle["height"], 0)
                    self.assertLessEqual(rectangle["x"] + rectangle["width"], 1.0000001)
                    self.assertLessEqual(rectangle["y"] + rectangle["height"], 1.0000001)

    def test_three_panel_layout_uses_a_primary_panel(self):
        layout = layout_panels(3, primary_index=0)
        roles = [item["role"] for item in layout["panels"]]
        self.assertEqual(roles.count("primary"), 1)
        self.assertTrue(layout["variable_panel_sizes"])

    def test_six_and_eight_use_two_column_panel_rows(self):
        six = layout_panels(6)
        eight = layout_panels(8)
        self.assertEqual(six["column_count"], 2)
        self.assertEqual(six["row_count"], 3)
        self.assertEqual(eight["column_count"], 2)
        self.assertEqual(eight["row_count"], 4)

    def test_figure_plan_records_layout_and_pdf_boundary(self):
        specs = [
            {"id": f"case_0:c{i}", "title": f"Chart {i}", "basis": "REAL"}
            for i in range(5)
        ]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "figure_plan.json"
            plan = write_figure_plan(specs, output)
            self.assertTrue(output.is_file())
            self.assertEqual(plan["layout"]["panel_count"], 5)
            self.assertEqual(
                plan["export_strategy"]["pdf_status"],
                "NOT_SUPPORTED_WITHOUT_LOCAL_VECTOR_CONVERTER",
            )

    def test_missing_exports_return_not_generated(self):
        with tempfile.TemporaryDirectory() as temp:
            result = compose_publication_svg(
                [{"id": "case_0:x", "title": "x"}],
                Path(temp) / "empty",
                Path(temp) / "figure.svg",
            )
            self.assertEqual(result["status"], "NOT_GENERATED")

    def test_supplied_svg_panels_compose_as_vector(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exports = root / "exports"
            exports.mkdir()
            chart_ids = {
                "chart_1.svg": "c",
                "chart_2.svg": "b",
                "chart_10.svg": "a",
            }
            for filename, chart_id in chart_ids.items():
                svg = (
                    '<svg xmlns="http://www.w3.org/2000/svg" '
                    'viewBox="0 0 400 240" data-pfc-chart-id="'
                    + chart_id
                    + '">'
                    '<path d="M0 0 L10 10" stroke="#3C5488"/></svg>'
                )
                (exports / filename).write_text(svg, encoding="utf-8")
            result = compose_publication_svg(
                [
                    {"id": "a", "title": "Speed–time"},
                    {"id": "b", "title": "Acceleration–time"},
                    {"id": "c", "title": "Correlation"},
                ],
                exports,
                root / "figure.svg",
            )
            self.assertEqual(result["status"], "GENERATED")
            self.assertTrue(result["vector"])
            self.assertEqual(result["layout_template"], "featured_plus_two")
            self.assertIn("Speed–time", (root / "figure.svg").read_text(encoding="utf-8"))
            self.assertEqual(
                [item["chart_id"] for item in result["identities"]],
                ["c", "b", "a"],
            )

    def test_unresolved_svg_identity_is_rejected(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240">'
            '<path d="M0 0 L10 10"/></svg>'
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exports = root / "exports"
            exports.mkdir()
            (exports / "chart_2.svg").write_text(svg, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "identity"):
                compose_publication_svg(
                    [{"id": "a", "title": "A"}],
                    exports,
                    root / "figure.svg",
                )

    def test_composer_removes_embedded_title_duplicate(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" '
            'data-pfc-chart-id="case_0:a">'
            '<g data-pfc-embedded-title="1"><text>Case title</text></g>'
            '<path d="M0 0 L10 10"/></svg>'
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exports = root / "exports"
            exports.mkdir()
            (exports / "chart_1.svg").write_text(svg, encoding="utf-8")
            compose_publication_svg(
                [{"id": "case_0:a", "title": "Case title"}],
                exports,
                root / "figure.svg",
            )
            output = (root / "figure.svg").read_text(encoding="utf-8")
            self.assertEqual(output.count("Case title"), 1)

    def test_more_than_26_panels_use_stable_alphabetic_labels(self):
        specs = [
            {"id": f"case_0:c{i}", "title": f"Chart {i}"}
            for i in range(27)
        ]
        with tempfile.TemporaryDirectory() as temp:
            plan = write_figure_plan(
                specs,
                Path(temp) / "figure_plan.json",
            )
            self.assertEqual(plan["panels"][0]["panel"], "a")
            self.assertEqual(plan["panels"][25]["panel"], "z")
            self.assertEqual(plan["panels"][26]["panel"], "aa")

    def test_publication_plan_groups_cases_and_limits_panels(self):
        specs = []
        for case_id in (0, 1, None):
            for index in range(8):
                specs.append(
                    {
                        "id": f"case_{case_id}:chart_{index}",
                        "case_id": case_id,
                        "title": f"Case {case_id} Chart {index}",
                        "decision": {"score": index / 10},
                    }
                )
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "figure_plan.json"
            plan = write_publication_plan(
                specs,
                output,
                max_panels_per_figure=6,
            )
            self.assertEqual(plan["figure_count"], 3)
            self.assertEqual(plan["selected_chart_count"], 18)
            self.assertEqual(plan["omitted_chart_count"], 6)
            for figure in plan["figures"]:
                self.assertLessEqual(figure["chart_count"], 6)
                self.assertEqual(
                    figure["chart_count"] + figure["omitted_chart_count"],
                    8,
                )
                self.assertTrue((output.parent / figure["specs_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
