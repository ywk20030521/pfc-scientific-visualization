"""PR4-PR6/PR8 visual and Console-boundary tests. NOT EXECUTED."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from viewer.linkage import evaluate_linkage_decisions

ROOT = Path(__file__).resolve().parents[1]


class ScientificVisualConsoleBoundaryTests(unittest.TestCase):
    def test_threejs_semantics_preserve_2d_and_instance_rendering(self):
        javascript = (ROOT / "assets" / "viewer" / "scientific-viewer.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("new THREE.InstancedMesh", javascript)
        self.assertIn("THREE.CircleGeometry(1, 32)", javascript)
        self.assertIn("THREE.SphereGeometry(1, 18, 12)", javascript)
        self.assertIn("renderer.outputColorSpace = THREE.SRGBColorSpace", javascript)
        self.assertIn("THREE.NoToneMapping", javascript)
        self.assertIn("renderer.shadowMap.enabled = true", javascript)
        self.assertIn("THREE.PCFSoftShadowMap", javascript)
        self.assertIn("highlightMesh = new THREE.InstancedMesh", javascript)
        self.assertIn('body.dataset.highlightPreservesPhysicalColor = "true"', javascript)
        self.assertNotIn("if (selected.has(ballId)) color = accentColor", javascript)

    def test_ball_highlight_is_an_overlay_not_a_color_replacement(self):
        javascript = (ROOT / "assets" / "viewer" / "scientific-viewer.js").read_text(
            encoding="utf-8"
        )
        update_particles = javascript.split("function updateParticles", 1)[1].split(
            "function updateWalls", 1
        )[0]
        self.assertIn("if (!Number.isFinite(value)) color = missingColor", update_particles)
        self.assertIn("highlightMesh.setMatrixAt", update_particles)
        self.assertIn("highlightMesh.count = selectedInstanceCount", update_particles)

    def test_publication_scene_export_composes_scientific_metadata(self):
        javascript = (ROOT / "assets" / "viewer" / "scientific-viewer.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("async function scenePublicationDataUrl", javascript)
        self.assertIn("includes_colorbar: true", javascript)
        self.assertIn("includes_cycle_and_time: true", javascript)
        self.assertIn("includes_scale_bar: true", javascript)
        self.assertIn('scene_svg: "NOT_SUPPORTED"', javascript)
        export_scene = javascript.split("async function exportScene", 1)[1].split(
            "async function exportFrame", 1
        )[0]
        self.assertIn("scenePublicationDataUrl", export_scene)
        self.assertNotIn("return renderSceneAt", export_scene)

    def test_acceleration_and_optional_networks_are_wired(self):
        shell = (ROOT / "assets" / "scientific-viewer-shell.html").read_text(
            encoding="utf-8"
        )
        javascript = (ROOT / "assets" / "viewer" / "scientific-viewer.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('value="acceleration"', shell)
        self.assertIn("updateNetworkLayers", javascript)
        self.assertIn("frame.contacts", javascript)
        self.assertIn("frame.bonds", javascript)

    def test_composite_export_uses_adaptive_layout_and_titles(self):
        javascript = (ROOT / "assets" / "viewer" / "scientific-viewer.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("function compositeLayout", javascript)
        self.assertIn("featured_plus_four", javascript)
        self.assertNotIn("const columns = 2;", javascript)
        self.assertIn("entry.panel.title.textContent", javascript)

    def test_viewer_shell_has_no_network_dependency(self):
        shell = (ROOT / "assets" / "scientific-viewer-shell.html").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("http://", shell)
        self.assertNotIn("https://", shell)
        self.assertIn("viewer/visual-semantics.js", shell)

    def test_linkage_is_selective_and_records_non_implementation(self):
        result = evaluate_linkage_decisions()
        by_id = {item["id"]: item for item in result["decisions"]}
        self.assertTrue(by_id["timeline_sync"]["implemented"])
        self.assertTrue(by_id["case_switch_sync"]["implemented"])
        self.assertFalse(by_id["particle_3d_to_2d_projection"]["implemented"])
        self.assertIn("decision_reason", by_id["particle_3d_to_2d_projection"])

    def test_capture_and_standardization_are_not_owned_here(self):
        forbidden = (
            "scripts/run_case.py",
            "scripts/capture_case.py",
            "scripts/validate_capture.py",
            "scripts/standardize/converter.py",
            "scripts/adapters/pfc_environment.py",
        )
        for relative in forbidden:
            self.assertFalse((ROOT / relative).exists(), relative)
        pipeline = (ROOT / "scripts" / "run_pipeline.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("verify_standard_contract", pipeline)
        self.assertNotIn("run_case", pipeline)
        self.assertNotIn("standardize_experiment", pipeline)

    def test_visual_semantics_and_chart_registry_are_valid_json(self):
        semantics = json.loads(
            (ROOT / "assets" / "styles" / "scientific-visual-semantics.json").read_text(
                encoding="utf-8"
            )
        )
        registry = json.loads(
            (ROOT / "assets" / "styles" / "chart-type-registry.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(semantics["truth_rules"]["interpolate_frames"], False)
        self.assertIn("heatmap", registry)
        self.assertIn("boxplot", registry)


if __name__ == "__main__":
    unittest.main()
