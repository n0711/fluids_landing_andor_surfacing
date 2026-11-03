"""Offline ROS3 + VERA evidence interoperability; never infer time alignment."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from space_landing.evidence_bundle import bundle
from space_landing.synthetic import SceneConfig, generate_dataset


class ExternalEvidenceBundleTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.dataset = self.root / "fixture"
        generate_dataset(self.dataset, SceneConfig(frames=6, width=64, height=64, fps=5, seed=11))
        self.ros = {
            "report_version": 1,
            "recording_parsed_to_eof": True,
            "recording_sha256": "a" * 64,
            "robot_id": "fixture-receiver",
            "stale_after_s": 1.0,
            "observation_count": 6,
            "payload_observation_count": 4,
            "silence_tick_count": 2,
            "accepted": 4,
            "rejected": 0,
            "observed_state_change_count": 3,
            "observed_stale_change_count": 1,
            "observed_stale_to_healthy_recoveries": 1,
            "final_state": "HEALTHY",
        }
        self.vera = {
            "vision_report_version": 1,
            "source": "vera-mot",
            "source_format": "motchallenge-10-column",
            "parsed_to_eof": True,
            "sequence": "synthetic_fixture",
            "mot_sha256": "b" * 64,
            "track_observation_rows": 6,
            "distinct_sequence_local_track_ids": 1,
            "frames_with_output": 6,
            "first_output_frame": 1,
            "last_output_frame": 6,
            "mean_rows_per_output_frame": 1.0,
        }

    def _file(self, name, data):
        file = self.root / name
        file.write_text(json.dumps(data), encoding="utf-8")
        return file

    def test_independent_reports_bundled_but_never_aligned(self):
        ros = self._file("ros.json", self.ros)
        vera = self._file("vera.json", self.vera)
        result = bundle(self.dataset, ros3_report=ros, vera_report=vera)
        self.assertEqual(result["cross_source_alignment"], "not_verified")
        self.assertEqual(result["robot_to_camera_sequence_mapping"], "not_verified")
        self.assertFalse(result["claims"]["cross_source_causal_agreement_established"])
        self.assertFalse(result["claims"]["ardupilot_sitl_connected_here"])
        self.assertEqual(result["ros3_receiver_evidence"]["accepted_receiver_payloads"], 4)
        self.assertEqual(result["vera_mot_tracker_evidence"]["frames_with_tracker_output"], 6)
        self.assertEqual(result["synthetic_fixture"]["metrics"]["fresh_arrival_stale_capture_ticks"], 2)
        self.assertEqual(result["ros3_receiver_evidence"]["report_sha256"],
                         hashlib.sha256(ros.read_bytes()).hexdigest())

    def test_only_ros3_is_legal_without_vision(self):
        r = bundle(self.dataset, ros3_report=self._file("ros.json", self.ros))
        self.assertIsNone(r["vera_mot_tracker_evidence"])

    def test_only_vision_is_legal_without_ros3(self):
        r = bundle(self.dataset, vera_report=self._file("vera.json", self.vera))
        self.assertIsNone(r["ros3_receiver_evidence"])

    def test_both_external_sources_missing_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            bundle(self.dataset)

    def test_ros3_requires_completed_upstream_parse(self):
        self.ros["recording_parsed_to_eof"] = False
        with self.assertRaisesRegex(ValueError, "EOF"):
            bundle(self.dataset, ros3_report=self._file("ros.json", self.ros))

    def test_ros3_counters_must_balance(self):
        self.ros["payload_observation_count"] = 5
        with self.assertRaisesRegex(ValueError, "counters"):
            bundle(self.dataset, ros3_report=self._file("ros.json", self.ros))

    def test_ros3_refuses_boolean_counters(self):
        self.ros["accepted"] = True
        with self.assertRaisesRegex(ValueError, "integer"):
            bundle(self.dataset, ros3_report=self._file("ros.json", self.ros))

    def test_vera_requires_valid_source_and_mean(self):
        self.vera["source"] = "unknown-tracker"
        with self.assertRaisesRegex(ValueError, "VERA"):
            bundle(self.dataset, vera_report=self._file("vera.json", self.vera))
        self.vera["source"] = "vera-mot"
        self.vera["mean_rows_per_output_frame"] = 7.0
        with self.assertRaisesRegex(ValueError, "counters"):
            bundle(self.dataset, vera_report=self._file("vera.json", self.vera))

    def test_vera_rejects_invalid_sequence_label(self):
        self.vera["sequence"] = "contains slash/"
        with self.assertRaisesRegex(ValueError, "sequence"):
            bundle(self.dataset, vera_report=self._file("vera.json", self.vera))

    def test_duplicate_json_keys_and_nonfinite_rejected(self):
        raw = '{"report_version":1,"report_version":1}\n'
        bad = self.root / "bad.json"
        bad.write_text(raw)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            bundle(self.dataset, ros3_report=bad)
        bad.write_text('{"report_version":NaN}')
        with self.assertRaisesRegex(ValueError, "non-finite"):
            bundle(self.dataset, ros3_report=bad)

    def test_recoveries_cannot_exceed_stale_transitions(self):
        self.ros["observed_stale_to_healthy_recoveries"] = 2
        with self.assertRaisesRegex(ValueError, "counters"):
            bundle(self.dataset, ros3_report=self._file("ros.json", self.ros))

    def test_huge_json_integer_is_not_accepted_as_timeout(self):
        self.ros["stale_after_s"] = 10**500
        with self.assertRaisesRegex(ValueError, "finite"):
            bundle(self.dataset, ros3_report=self._file("ros.json", self.ros))

    def test_oversized_json_is_rejected(self):
        huge = self.root / "huge.json"
        huge.write_bytes(b"x" * 1_000_001)
        with self.assertRaisesRegex(ValueError, "1 MB"):
            bundle(self.dataset, ros3_report=huge)


if __name__ == "__main__":
    unittest.main()
