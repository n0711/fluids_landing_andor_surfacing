"""End-to-end hosted-runner artifact and scientific-claim separation tests."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.ci_evidence import build_evidence


class EvidenceReceiptTests(unittest.TestCase):
    def test_receipt_hashes_and_claims(self):
        with tempfile.TemporaryDirectory() as scratch:
            out = Path(scratch) / "evidence"
            receipt = build_evidence(out)
            self.assertTrue(receipt["claims"]["all_data_synthetic"])
            self.assertTrue(receipt["claims"]["oracle_is_ground_truth_not_trained_model"])
            self.assertFalse(receipt["claims"]["vera_mot_model_executed"])
            self.assertFalse(receipt["claims"]["ardupilot_sitl_executed"])
            self.assertFalse(receipt["claims"]["ros3_executed"])
            pairs = [
                ("integrity-comparison.json", "comparison_report_sha256"),
                ("oracle-format-check.json", "oracle_format_report_sha256"),
            ]
            for path, field in pairs:
                digest = hashlib.sha256((out / path).read_bytes()).hexdigest()
                self.assertEqual(digest, receipt[field])
            manifest = json.loads((out / "synthetic-fixture" / "manifest.json").read_text())
            self.assertEqual(receipt["dataset_observations_sha256"],
                             manifest["observations_sha256"])
            self.assertTrue((out / "evidence-receipt.json").exists())

    def test_comparison_is_byte_identical_in_clean_runs(self):
        with tempfile.TemporaryDirectory() as scratch:
            a, b = Path(scratch) / "a", Path(scratch) / "b"
            build_evidence(a)
            build_evidence(b)
            for path in ("integrity-comparison.json", "oracle-format-check.json",
                         "synthetic-fixture/observations.jsonl",
                         "synthetic-ground-truth-oracle.mot"):
                self.assertEqual((a / path).read_bytes(), (b / path).read_bytes())

    def test_does_not_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as scratch:
            out = Path(scratch) / "output"
            build_evidence(out)
            with self.assertRaises(FileExistsError):
                build_evidence(out)


if __name__ == "__main__":
    unittest.main()
