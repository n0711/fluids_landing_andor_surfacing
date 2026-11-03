"""Remote CI-only reproducible evidence builder (synthetic data, stdlib only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from space_landing.integrity import compare_scenarios
from space_landing.mot_evaluation import evaluate_mot
from space_landing.synthetic import SceneConfig, generate_dataset, validate_dataset


def _write_json(path: Path, value: dict) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def build_evidence(output: Path) -> dict:
    """Build the same evidence from scratch on a GitHub runner, never a vehicle."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    directory = output / "synthetic-fixture"
    cfg = SceneConfig(frames=6, width=64, height=64, fps=5, seed=11)
    manifest = generate_dataset(directory, cfg)
    assert validate_dataset(directory) == cfg.frames

    comparison = compare_scenarios(directory)
    integrity_hash = _write_json(output / "integrity-comparison.json", comparison)

    # Deliberately use exact ground truth as an "oracle", to validate the file
    # adapter and detection arithmetic. This is NOT a VERA-MOT model result.
    observations = [
        json.loads(line)
        for line in (directory / "observations.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    mot = "\n".join(
        f"{index},1,{','.join(map(str, obs['objects'][0]['bbox_xywh']))},1,-1,-1,-1"
        for index, obs in enumerate(observations, 1)
    ) + "\n"
    oracle_file = output / "synthetic-ground-truth-oracle.mot"
    oracle_file.write_text(mot, encoding="utf-8")
    detection = evaluate_mot(directory, oracle_file)
    detection_hash = _write_json(output / "oracle-format-check.json", detection)

    scenarios = {row["scenario"]: row for row in comparison["scenarios"]}
    assert scenarios["nominal"]["telemetry_vs_vision_divergence_ticks"] == 0
    assert scenarios["replayed_frame"]["fresh_arrival_stale_capture_ticks"] == 2
    assert scenarios["vision_silence"]["fresh_arrival_stale_capture_ticks"] == 0
    assert scenarios["lagged_capture"]["fresh_arrival_stale_capture_ticks"] == 4
    assert detection["metrics"]["precision"] == 1.0
    assert detection["metrics"]["recall"] == 1.0

    receipt = {
        "receipt_version": 1,
        "experiment": "synthetic_observation_integrity_v1",
        "repository_commit": os.environ.get("GITHUB_SHA", "not_recorded"),
        "dataset_observations_sha256": manifest["observations_sha256"],
        "comparison_report_sha256": integrity_hash,
        "oracle_format_report_sha256": detection_hash,
        "claims": {
            "all_data_synthetic": True,
            "oracle_is_ground_truth_not_trained_model": True,
            "vera_mot_model_executed": False,
            "ardupilot_sitl_executed": False,
            "ros3_executed": False,
            "spaceflight_validation": False,
        },
        "interpretation": (
            "This CI check tests observation accounting, provenance, and "
            "MOT text compatibility. It does not execute VERA-MOT inference, "
            "ArduPilot SITL, ROS3, or physical landing dynamics."
        ),
    }
    _write_json(output / "evidence-receipt.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    receipt = build_evidence(args.out)
    print(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
