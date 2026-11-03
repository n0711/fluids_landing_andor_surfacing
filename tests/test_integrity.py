"""Reproducible counterfactual and VERA-compatible offline evidence tests."""

import json
from pathlib import Path
import tempfile
import unittest

from space_landing.integrity import SCENARIOS, audit, compare_scenarios
from space_landing.mot_evaluation import evaluate_mot, parse_mot
from space_landing.synthetic import SceneConfig, generate_dataset


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.dataset = self.root / "images"
        generate_dataset(self.dataset, SceneConfig(frames=6, width=64, height=64, fps=5, seed=11))

    def _oracle(self):
        rows = [json.loads(line) for line in (self.dataset / "observations.jsonl").read_text().splitlines()]
        return "".join(
            f"{i},1,{','.join(map(str, row['objects'][0]['bbox_xywh']))},1,-1,-1,-1\n"
            for i, row in enumerate(rows, start=1)
        )

    def _write_mot(self, text):
        path = self.root / "tracker.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def test_nominal_observer_has_no_disagreement(self):
        report = audit(self.dataset, "nominal")
        self.assertEqual(report["metrics"]["telemetry_vs_vision_divergence_ticks"], 0)
        self.assertEqual(report["metrics"]["fresh_arrival_stale_capture_ticks"], 0)
        self.assertTrue(all(x["vision_capture_recent"] for x in report["ledger"]))

    def test_silence_detected_by_transport_and_capture(self):
        report = audit(self.dataset, "vision_silence")
        self.assertEqual(report["metrics"]["vision_arrival_ticks"], 3)
        self.assertEqual(report["metrics"]["telemetry_vs_vision_divergence_ticks"], 2)
        self.assertEqual(report["metrics"]["fresh_arrival_stale_capture_ticks"], 0)
        self.assertEqual(report["metrics"]["telemetry_recent_ticks"], 6)

    def test_frozen_capture_masquerading_as_recent_arrival(self):
        report = audit(self.dataset, "replayed_frame")
        self.assertEqual(report["metrics"]["vision_arrival_ticks"], 6)
        self.assertEqual(report["metrics"]["transport_recent_ticks"], 6)
        self.assertEqual(report["metrics"]["fresh_arrival_stale_capture_ticks"], 2)
        self.assertTrue(report["ledger"][4]["vision_transport_recent"])
        self.assertFalse(report["ledger"][4]["vision_capture_recent"])
        self.assertEqual(report["ledger"][4]["received_source_frame"], 1)

    def test_lagged_capture_is_independent_of_heartbeat(self):
        report = audit(self.dataset, "lagged_capture")
        self.assertEqual(report["metrics"]["fresh_arrival_stale_capture_ticks"], 4)
        self.assertEqual(report["metrics"]["telemetry_vs_vision_divergence_ticks"], 4)

    def test_comparison_is_reproducible_and_provenance_bounded(self):
        first = compare_scenarios(self.dataset)
        second = compare_scenarios(self.dataset)
        self.assertEqual(first, second)
        self.assertEqual([r["scenario"] for r in first["scenarios"]], list(SCENARIOS))
        self.assertEqual(first["scenarios"][2]["fresh_arrival_stale_capture_ticks"], 2)
        self.assertFalse(audit(self.dataset, "nominal")["claims"]["ardupilot_connected"])

    def test_unknown_scenario_fails(self):
        with self.assertRaises(ValueError):
            audit(self.dataset, "hardware_validation")

    def test_single_frame_insufficient_for_time_audit(self):
        tiny = self.root / "single"
        generate_dataset(tiny, SceneConfig(frames=1))
        with self.assertRaisesRegex(ValueError, "at least two"):
            audit(tiny, "nominal")

    def test_oracle_mot_overlap_is_one_without_identity_claim(self):
        path = self._write_mot(self._oracle())
        report = evaluate_mot(self.dataset, path)
        m = report["metrics"]
        self.assertEqual((m["true_positive"], m["false_positive"], m["false_negative"]), (6, 0, 0))
        self.assertEqual((m["precision"], m["recall"], m["mean_iou_matched_only"]), (1.0, 1.0, 1.0))
        self.assertFalse(report["claims"]["reid_identity_accuracy_established"])
        self.assertFalse(report["claims"]["vera_mot_executed_by_this_evaluator"])

    def test_offset_boxes_are_not_matches(self):
        predictions = self._oracle().splitlines()
        parts = predictions[0].split(",")
        parts[2] = "10000"
        predictions[0] = ",".join(parts)
        report = evaluate_mot(self.dataset, self._write_mot("\n".join(predictions) + "\n"))
        self.assertEqual((report["metrics"]["true_positive"], report["metrics"]["false_positive"],
                          report["metrics"]["false_negative"]), (5, 1, 1))

    def test_missing_frames_are_not_mistaken_for_zero_ground_truth(self):
        only_first = self._oracle().splitlines()[0] + "\n"
        report = evaluate_mot(self.dataset, self._write_mot(only_first))
        self.assertEqual(report["metrics"]["frames_with_mot_output"], 1)
        self.assertEqual(report["metrics"]["false_negative"], 5)

    def test_duplicate_track_id_is_rejected(self):
        first = self._oracle().splitlines()[0]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_mot((first + "\n" + first + "\n").encode(), 6)

    def test_out_of_order_and_nonfinite_mot_rejected(self):
        first, second = self._oracle().splitlines()[:2]
        with self.assertRaisesRegex(ValueError, "sorted"):
            parse_mot((second + "\n" + first + "\n").encode(), 6)
        invalid = first.split(",")
        invalid[2] = "nan"
        with self.assertRaisesRegex(ValueError, "finite"):
            parse_mot((",".join(invalid) + "\n").encode(), 6)

    def test_out_of_range_frames_are_rejected(self):
        first = self._oracle().splitlines()[0]
        broken = first.split(",")
        broken[0] = "7"
        with self.assertRaisesRegex(ValueError, "frame/track"):
            parse_mot((",".join(broken) + "\n").encode(), 6)


if __name__ == "__main__":
    unittest.main()
