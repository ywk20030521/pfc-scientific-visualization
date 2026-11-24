from __future__ import annotations

import base64
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from analysis import analyze_experiment
from viewer import build_viewer


ROOT = Path(__file__).resolve().parents[1]
STANDARDIZED_SAMPLE = (
    ROOT / "examples" / "standardized_data" / "Mock_Experiment"
)


def _registered_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return json.loads(text[text.find("{") : text.rfind("}") + 1])


class ChunkedViewerTests(unittest.TestCase):
    def test_real_frames_are_externalized_and_payload_can_be_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            result_root = Path(temp) / "Result"
            standardized = result_root / "Standardized"
            analysis_root = result_root / "03_analysis"
            shutil.copytree(STANDARDIZED_SAMPLE, standardized)
            experiment = json.loads(
                (standardized / "experiment.json").read_text(encoding="utf-8")
            )
            analyze_experiment(standardized, analysis_root)
            output = result_root / "04_viewer" / "scientific_viewer.html"
            manifest = build_viewer(
                standardized,
                output,
                analysis_root=analysis_root,
                max_frames=0,
                title="Mock Viewer Test",
            )

            self.assertLess(manifest["html_bytes"], 5 * 1024 * 1024)
            html = output.read_text(encoding="utf-8")
            self.assertNotIn("PFC_DATA", html)
            self.assertIn("data/catalog.js", html)
            self.assertTrue((output.parent / "viewer" / "scientific-viewer.js").is_file())
            self.assertFalse((output.parent / "data" / "catalog.js").read_text(encoding="utf-8").strip() == "")
            linkage = json.loads(
                (output.parent / "linkage_decisions.json").read_text(encoding="utf-8")
            )
            self.assertEqual(linkage["status"], "GENERATED")
            self.assertTrue(any(item["implemented"] for item in linkage["decisions"]))

            catalog = _registered_json(output.parent / "data" / "catalog.js")
            for case in experiment["cases"]:
                case_id = int(case["case_id"])
                summary = next(item for item in catalog["cases"] if int(item["id"]) == case_id)
                self.assertEqual(summary["viewerFrameCount"], summary["sourceFrameCount"])
                meta = _registered_json(output.parent / "data" / "cases" / f"case_{case_id}" / "meta.js")
                self.assertEqual(meta["viewerFrameCount"], meta["sourceFrameCount"])
                first = meta["frames"][0]
                chunk = _registered_json(
                    output.parent
                    / "data"
                    / "cases"
                    / f"case_{case_id}"
                    / "chunks"
                    / f"chunk_{first['chunk']:03d}.js"
                )
                ids = np.frombuffer(
                    base64.b64decode(chunk["frames"][first["chunkOffset"]]["ids"]),
                    dtype="<u4",
                )
                self.assertEqual(len(ids), first["ballCount"])

            catalog_path = output.parent / "data" / "catalog.js"
            before = catalog_path.stat().st_mtime_ns
            second = build_viewer(
                standardized,
                output,
                analysis_root=analysis_root,
                max_frames=0,
                title="Mock Viewer Test",
            )
            self.assertTrue(second["payload"]["reused"])
            self.assertEqual(catalog_path.stat().st_mtime_ns, before)

    def test_analysis_arrays_are_finite_for_complete_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            result_root = Path(temp) / "Result"
            standardized = result_root / "Standardized"
            analysis_root = result_root / "03_analysis"
            shutil.copytree(STANDARDIZED_SAMPLE, standardized)
            analyze_experiment(standardized, analysis_root)
            experiment = json.loads((standardized / "experiment.json").read_text(encoding="utf-8"))
            arrays_path = standardized / experiment["cases"][0]["arrays_path"]
            with np.load(analysis_root / "case_0" / "analysis_arrays.npz", allow_pickle=False) as analysis:
                values = analysis["ball_displacement_magnitude"]
                self.assertIn("ball_acceleration_magnitude", analysis.files)
            self.assertTrue(np.isfinite(values).all())
            self.assertTrue(arrays_path.is_file())

    def test_multi_case_static_payload_is_not_merged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            standardized = root / "Result" / "Standardized"
            shutil.copytree(STANDARDIZED_SAMPLE, standardized)
            analysis_root = root / "Result" / "03_analysis"
            experiment_path = standardized / "experiment.json"
            experiment = json.loads(
                experiment_path.read_text(encoding="utf-8")
            )
            second_case = json.loads(json.dumps(experiment["cases"][0]))
            second_case["case_id"] = 1
            second_case["run_id"] = "mock-case-1"
            second_case["arrays_path"] = "cases/case_1/arrays.npz"
            shutil.copytree(
                standardized / "cases" / "case_0",
                standardized / "cases" / "case_1",
            )
            case_record_path = standardized / "cases" / "case_1" / "case.json"
            case_record = json.loads(case_record_path.read_text(encoding="utf-8"))
            case_record["case_id"] = 1
            case_record["run_id"] = "mock-case-1"
            case_record_path.write_text(
                json.dumps(case_record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            experiment["cases"].append(second_case)
            experiment_path.write_text(
                json.dumps(experiment, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            analyze_experiment(standardized, analysis_root)
            output = root / "Result" / "04_viewer" / "scientific_viewer.html"
            build_viewer(
                standardized,
                output,
                analysis_root=analysis_root,
                title="Multi Case",
            )
            static = _registered_json(output.parent / "data" / "static.js")
            self.assertEqual(set(static["cases"]), {"0", "1"})
            self.assertEqual(
                len(static["cases"]["0"]["balls"]),
                len(static["cases"]["1"]["balls"]),
            )


if __name__ == "__main__":
    unittest.main()
