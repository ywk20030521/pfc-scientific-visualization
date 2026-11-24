from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from maintenance.cleanup_delivery import apply_cleanup, plan_cleanup


class CleanupSafetyTests(unittest.TestCase):
    def test_plan_and_apply_only_generated_intermediates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Experiment"
            (root / "03_analysis").mkdir(parents=True)
            (root / "work").mkdir()
            (root / "work" / "cache.txt").write_text("temporary", encoding="utf-8")
            (root / "failed_pipeline_attempt_1").mkdir()
            (root / "failed_pipeline_attempt_1" / "result.json").write_text("{}", encoding="utf-8")
            (root / "work_with_raw").mkdir()
            (root / "work_with_raw" / "model.sav").write_bytes(b"do not delete")

            plan = plan_cleanup(root)
            accepted = {item["path"] for item in plan["accepted"]}
            skipped = {item["path"] for item in plan["skipped"]}
            self.assertEqual(accepted, {"work", "failed_pipeline_attempt_1"})
            self.assertIn("work_with_raw", skipped)
            self.assertTrue((root / "work").exists())

            result = apply_cleanup(root, plan, "CLEAN_INTERMEDIATE")
            self.assertTrue(result["applied"])
            self.assertFalse((root / "work").exists())
            self.assertFalse((root / "failed_pipeline_attempt_1").exists())
            self.assertTrue((root / "work_with_raw" / "model.sav").is_file())
            self.assertTrue((root / "07_metadata" / "cleanup_report.json").is_file())

    def test_wrong_confirmation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "03_analysis").mkdir()
            (root / "work").mkdir()
            plan = plan_cleanup(root)
            with self.assertRaisesRegex(RuntimeError, "Confirmation"):
                apply_cleanup(root, plan, "yes")
            self.assertTrue((root / "work").exists())

    def test_standardized_contract_cannot_be_cleanup_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "delivery_manifest.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "standardized contract"):
                plan_cleanup(root)


if __name__ == "__main__":
    unittest.main()
