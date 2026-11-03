"""Verifier unit tests use fabricated summaries; CI separately executes exporters."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.ci_evidence import build_evidence
from scripts.verify_upstream_ci import verify
from space_landing.evidence_bundle import bundle


class CloudEvidenceVerifierTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "evidence"
        build_evidence(self.root)
        recording = self.root / "ros3-demo.jsonl"
        recording.write_bytes(b"synthetic placeholder only, not upstream execution\n")
        source_mot = self.root / "synthetic-ground-truth-oracle.mot"
        ros3 = {
            "report_version": 1,
            "recording_parsed_to_eof": True,
            "recording_sha256": hashlib.sha256(recording.read_bytes()).hexdigest(),
            "robot_id": "usv01",
            "stale_after_s": 1.0,
            "observation_count": 6,
            "payload_observation_count": 4,
            "silence_tick_count": 2,
            "accepted": 4,
            "rejected": 0,
            "observed_stale_change_count": 1,
            "observed_state_change_count": 3,
            "observed_stale_to_healthy_recoveries": 1,
            "final_state": "HEALTHY",
        }
        vera = {
            "vision_report_version": 1,
            "source": "vera-mot",
            "source_format": "motchallenge-10-column",
            "parsed_to_eof": True,
            "sequence": "synthetic_fixture",
            "mot_sha256": hashlib.sha256(source_mot.read_bytes()).hexdigest(),
            "track_observation_rows": 6,
            "distinct_sequence_local_track_ids": 1,
            "frames_with_output": 6,
            "first_output_frame": 1,
            "last_output_frame": 6,
            "mean_rows_per_output_frame": 1.0,
        }
        (self.root / "ros3-evidence.json").write_text(json.dumps(ros3), encoding="utf-8")
        (self.root / "vera-evidence.json").write_text(json.dumps(vera), encoding="utf-8")
        output = bundle(
            self.root / "synthetic-fixture",
            ros3_report=self.root / "ros3-evidence.json",
            vera_report=self.root / "vera-evidence.json",
        )
        (self.root / "offline-bundle.json").write_text(json.dumps(output), encoding="utf-8")

    def test_verifier_marks_physical_and_clock_claims_false(self):
        result = verify(self.root)
        self.assertTrue(result["checks"]["bundle_recomputed_equal"])
        self.assertFalse(result["checks"]["clock_alignment_verified"])
        self.assertFalse(result["checks"]["vera_model_inference_performed"])
        self.assertFalse(result["checks"]["ardupilot_sitl_executed"])

    def test_verifier_detects_modified_upstream_recording(self):
        file = self.root / "ros3-demo.jsonl"
        file.write_bytes(file.read_bytes() + b"modified\n")
        with self.assertRaisesRegex(ValueError, "ROS3 source-recording fingerprint"):
            verify(self.root)

    def test_verifier_detects_modified_source_tracker_file(self):
        file = self.root / "synthetic-ground-truth-oracle.mot"
        file.write_bytes(file.read_bytes() + b"7,1,0,0,10,10,1,-1,-1,-1\n")
        with self.assertRaisesRegex(ValueError, "VERA-MOT source-file fingerprint"):
            verify(self.root)

    def test_verifier_rejects_edited_cross_source_bundle(self):
        path = self.root / "offline-bundle.json"
        obj = json.loads(path.read_text())
        obj["cross_source_alignment"] = "verified"
        path.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError, "differs"):
            verify(self.root)

    def test_verifier_rejects_missing_report(self):
        (self.root / "vera-evidence.json").unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
