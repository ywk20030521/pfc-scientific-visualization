"""Contract checks for the light-only, bottom-dock scientific viewer upgrade."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "assets" / "scientific-viewer-shell.html"
CSS = ROOT / "assets" / "viewer" / "scientific-viewer.css"
JS = ROOT / "assets" / "viewer" / "scientific-viewer.js"
SEMANTICS = ROOT / "assets" / "styles" / "scientific-visual-semantics.json"


class ViewerUpgradeContractTests(unittest.TestCase):
    def test_layout_ids_and_light_only_shell(self) -> None:
        shell = SHELL.read_text(encoding="utf-8")
        for element_id in (
            "dockToggle", "controlDock", "colorPalette", "showInsets",
            "topInsetCanvas", "sectionInsetCanvas", "summaryBody",
            "resetCamera", "playButton", "timeline", "exportPanels", "chartGrid",
        ):
            self.assertIn(f'id="{element_id}"', shell)
        self.assertNotIn('id="themeToggle"', shell)
        self.assertIn('data-theme="light"', shell)
        self.assertIn('aria-expanded="false"', shell)

    def test_golden_ratio_layout_and_dock_css(self) -> None:
        css = CSS.read_text(encoding="utf-8")
        self.assertIn("grid-template-columns: minmax(0, 1.618fr) minmax(460px, 1fr)", css)
        self.assertIn("#controlDock.collapsed { display: none; }", css)
        self.assertIn("height: var(--dock-max-height)", css)
        self.assertIn('body[data-dock="collapsed"] .section-inset', css)
        self.assertNotIn(':root[data-theme="dark"]', css)

    def test_runtime_uses_light_scientific_preset_and_insets(self) -> None:
        js = JS.read_text(encoding="utf-8")
        self.assertIn("const documentTheme = \"light\";", js)
        self.assertIn("THREE.ACESFilmicToneMapping", js)
        self.assertIn("THREE.MeshPhysicalMaterial", js)
        self.assertIn("envMapIntensity: 1.4", js)
        self.assertIn("function drawInsets", js)
        self.assertIn("body.dataset.insetChoice", js)
        self.assertIn("byId(\"colorPalette\").addEventListener", js)
        self.assertIn("runtime.viewShift", js)
        self.assertIn("wallSolids = new THREE.InstancedMesh", js)
        self.assertIn('choice === "both" || choice === "section"', js)

    def test_light_ramp_is_the_validated_palette(self) -> None:
        semantics = SEMANTICS.read_text(encoding="utf-8")
        self.assertIn('"#5B9BD5"', semantics)
        self.assertIn('"#E46A3C"', semantics)
        self.assertNotIn('"#2b3a63"', semantics)


class BugFixContractTests(unittest.TestCase):
    """Contracts for the 2026-11-23 bug-fix round."""

    def test_summary_is_always_visible_without_toggle_button(self) -> None:
        shell = SHELL.read_text(encoding="utf-8")
        self.assertIn('<div id="summaryInline" class="summary-inline">', shell)
        self.assertIn('class="summary-inline-title"', shell)
        self.assertNotIn("<summary>", shell)
        self.assertNotIn("<details", shell)
        css = CSS.read_text(encoding="utf-8")
        self.assertIn(".summary-inline-title", css)

    def test_dynamic_cracks_via_endpoint_ball_ids(self) -> None:
        js = JS.read_text(encoding="utf-8")
        self.assertIn("positionById", js)
        self.assertIn("row[9]", js)
        self.assertIn("row[10]", js)
        builder = (ROOT / "scripts" / "viewer" / "payload_builder.py").read_text(encoding="utf-8")
        self.assertIn("fracture_ball_id_a", builder)
        self.assertIn("fracture_ball_id_b", builder)

    def test_2d_hides_clip_and_insets(self) -> None:
        js = JS.read_text(encoding="utf-8")
        self.assertIn('body.dataset.dimension = String(is2D ? 2 : 3)', js)
        self.assertIn('body.dataset.insetChoice = "none"', js)
        css = CSS.read_text(encoding="utf-8")
        self.assertIn('body[data-dimension="2"] .dim3-only', css)
        self.assertIn('body[data-dimension="2"] .scene-inset', css)
        shell = SHELL.read_text(encoding="utf-8")
        self.assertIn('id="showClip" type="checkbox"', shell)
        self.assertIn('class="dim3-only"', shell)

    def test_headless_contact_field_compatibility(self) -> None:
        builder = (ROOT / "scripts" / "viewer" / "payload_builder.py").read_text(encoding="utf-8")
        # Real headless converter contract names.
        self.assertIn('f"{prefix}_offsets"', builder)
        self.assertIn('f"{prefix}_end1_id"', builder)
        self.assertIn('f"{prefix}_end2_id"', builder)
        self.assertIn('f"{prefix}_force_xyz"', builder)
        self.assertIn("np.linalg.norm(vectors, axis=1)", builder)
        # Legacy/extended names remain supported.
        self.assertIn('f"{prefix}_ball_id_a"', builder)
        self.assertIn('f"{prefix}_force_n"', builder)


if __name__ == "__main__":
    unittest.main()
