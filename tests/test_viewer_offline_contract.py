"""Viewer source and offline-contract tests.  NOT EXECUTED in delivery."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "scientific-viewer-template.html"


class ViewerContractTests(unittest.TestCase):
    def test_template_uses_local_vendor_placeholders_only(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("__THREE_JS__", text)
        self.assertIn("__ORBIT_JS__", text)
        self.assertIn("__ECHARTS_JS__", text)
        self.assertNotIn("https://cdn", text)
        self.assertNotIn("http://cdn", text)

    def test_dynamic_particle_updates_reuse_instanced_mesh(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("THREE.InstancedMesh", text)
        self.assertIn("particles.setMatrixAt", text)
        self.assertIn("frame.displacements", text)
        self.assertNotIn("new THREE.SphereGeometry(1,12,8)", text.split("function updateParticles")[1])

    def test_case_switch_releases_chart_resources(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("chart.dispose()", text)
        self.assertIn("disposeCharts", text)

    def test_publication_exports_and_tracking_are_exposed(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("window.PFCViewer", text)
        self.assertIn("exportPNG", text)
        self.assertIn("exportChartSVGs", text)
        self.assertIn("buildTrajectory", text)
        self.assertIn("INSUFFICIENT_REAL_SAMPLES", text)

    def test_missing_cracks_are_labeled_not_zero_filled(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('"未采集"', text)


if __name__ == "__main__":
    unittest.main()
