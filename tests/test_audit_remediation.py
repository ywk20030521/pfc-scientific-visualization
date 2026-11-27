"""Audit remediation: canonical layers and analysis-feedback classification."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from schema.layer_contract import (  # noqa: E402
    CANONICAL_LAYERS, can_write, normalize_layer,
)


class AuditRemediationTests(unittest.TestCase):
    def test_legacy_layers_normalize_to_canonical_vocabulary(self):
        self.assertEqual(CANONICAL_LAYERS, ("RAW", "STANDARDIZED", "DERIVED"))
        self.assertEqual(normalize_layer("RAW_DATA"), "RAW")
        self.assertEqual(normalize_layer("ANALYSIS_DATA"), "DERIVED")
        self.assertEqual(normalize_layer("DISPLAY_DATA"), "DERIVED")
        with self.assertRaises(ValueError):
            normalize_layer("NOT_A_LAYER")

    def test_derived_layer_owned_by_visualization_only(self):
        self.assertTrue(can_write("pfc-scientific-visualization", "DERIVED"))
        self.assertFalse(can_write("pfc-headless", "DERIVED"))
        self.assertFalse(can_write("pfc-interaction", "RAW"))

    def test_schema_marks_analysis_feedback_as_not_re_finding(self):
        schema = json.loads(
            (SCRIPTS.parent / "schema" / "analysis_findings.schema.json").read_text(
                encoding="utf-8")
        )
        self.assertIn("classification", schema["required"])
        self.assertIn("finding_authority", schema["required"])
        self.assertEqual(
            schema["properties"]["finding_authority"]["const"], "NOT_RE_FINDING")


if __name__ == "__main__":
    unittest.main()
