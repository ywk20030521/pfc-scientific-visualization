from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from emit_findings import build_findings  # noqa: E402


class AnalysisFindingsProducerTests(unittest.TestCase):
    def test_producer_emits_missing_channels_and_source_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "deliveries" / "run_001"
            source.mkdir(parents=True)
            (source / "experiment.json").write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "case_id": 0,
                                "channels": [
                                    {
                                        "id": "contact_id",
                                        "status": "NOT_CAPTURED",
                                        "source": "NOT_CAPTURED",
                                    },
                                    {
                                        "id": "ball_xyz",
                                        "status": "GENERATED",
                                        "source": "REAL_PFC",
                                    },
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            analysis = root / "analysis" / "run_001_visualization"
            (analysis / "03_analysis").mkdir(parents=True)
            (analysis / "07_metadata").mkdir(parents=True)
            (analysis / "03_analysis" / "analysis.json").write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "case_id": 0,
                                "channels": [
                                    {
                                        "id": "ball.displacement",
                                        "status": "GENERATED",
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (analysis / "07_metadata" / "experiment_capabilities.json").write_text(
                json.dumps({"cases": {"0": {"dimension": 2}}}),
                encoding="utf-8",
            )
            (analysis / "07_metadata" / "source_contract.json").write_text(
                json.dumps(
                    {
                        "root": str(source),
                        "manifest_sha256": "a" * 64,
                        "experiment_id": "run_001",
                    }
                ),
                encoding="utf-8",
            )
            findings = build_findings(analysis, project_root=root)
            self.assertEqual(findings["contract"], "pfc.analysis-findings@1.0.0")
            self.assertEqual(findings["run_id"], "run_001")
            self.assertIn("contact_id", findings["missing_data"])
            self.assertTrue(findings["recommended_sampling"]["capture_contacts"])
            self.assertEqual(
                findings["source_contract"]["manifest_sha256"],
                "a" * 64,
            )
            self.assertTrue(
                all(
                    (root / item).is_file()
                    for item in findings["referenced_artifacts"]
                )
            )


class PortableFeedbackArtifactTests(unittest.TestCase):
    def test_outside_project_root_artifacts_are_copied_inside(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "deliveries" / "run_001"
            source.mkdir(parents=True)
            (source / "experiment.json").write_text('{"cases": []}', encoding="utf-8")
            analysis = root / "analysis_outside" / "run_001_visualization"
            (analysis / "03_analysis").mkdir(parents=True)
            (analysis / "07_metadata").mkdir(parents=True)
            (analysis / "03_analysis" / "analysis.json").write_text(
                '{"cases": []}', encoding="utf-8"
            )
            (analysis / "07_metadata" / "experiment_capabilities.json").write_text(
                '{"cases": {"0": {"dimension": 2}}}', encoding="utf-8"
            )
            (analysis / "07_metadata" / "source_contract.json").write_text(
                json.dumps({
                    "root": str(source),
                    "manifest_sha256": "b" * 64,
                    "experiment_id": "run_001",
                }),
                encoding="utf-8",
            )
            project = root / "headless"
            project.mkdir()
            findings = build_findings(analysis, project_root=project)
            for relative in findings["referenced_artifacts"]:
                self.assertFalse(Path(relative).is_absolute())
                self.assertTrue((project / relative).is_file())
            self.assertEqual(
                len(findings["source_contract"]["artifact_sha256"]), 3
            )


if __name__ == "__main__":
    unittest.main()
