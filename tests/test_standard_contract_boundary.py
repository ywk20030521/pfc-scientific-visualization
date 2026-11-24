from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from run_pipeline import run_pipeline
from standard_contract import StandardContractError, verify_standard_contract


ROOT = Path(__file__).resolve().parents[1]
STANDARDIZED_SAMPLE = ROOT / "examples" / "standardized_data" / "Mock_Experiment"


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class StandardContractBoundaryTests(unittest.TestCase):
    def test_analysis_consumes_read_only_contract_and_writes_separate_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            standardized = root / "Standardized"
            output = root / "Analysis"
            shutil.copytree(STANDARDIZED_SAMPLE, standardized)
            before = _tree_hashes(standardized)
            result = run_pipeline(standardized, output, max_frames=0)
            after = _tree_hashes(standardized)
            self.assertEqual(before, after)
            self.assertEqual(result["source_contract"]["name"], "pfc.standardized-experiment")
            self.assertFalse((output / "01_raw_data").exists())
            self.assertFalse((output / "02_standardized_data").exists())
            source = json.loads(
                (output / "07_metadata" / "source_contract.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(source["status"], "VERIFIED_READ_ONLY")
            self.assertEqual(source["owner"], "pfc-headless")
            layers = json.loads(
                (output / "03_analysis" / "data_layers.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(layers["layers"], ["ANALYSIS_DATA", "DISPLAY_DATA"])
            self.assertTrue(layers["external_parent"]["read_only"])

    def test_tampered_contract_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            standardized = Path(temp) / "Standardized"
            shutil.copytree(STANDARDIZED_SAMPLE, standardized)
            arrays = standardized / "cases" / "case_0" / "arrays.npz"
            arrays.write_bytes(arrays.read_bytes() + b"tampered")
            with self.assertRaisesRegex(StandardContractError, "size|hash"):
                verify_standard_contract(standardized)

    def test_analysis_output_cannot_nest_inside_source_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            standardized = Path(temp) / "Standardized"
            shutil.copytree(STANDARDIZED_SAMPLE, standardized)
            with self.assertRaisesRegex(ValueError, "separate"):
                run_pipeline(
                    standardized,
                    standardized / "Analysis",
                    max_frames=0,
                )


if __name__ == "__main__":
    unittest.main()
