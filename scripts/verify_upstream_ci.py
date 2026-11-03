"""Validate hosted synthetic ROS3 and VERA exporter artifacts, fail closed.

Upstream module execution is established by the GitHub Actions steps/logs, not
by this post-hoc file verifier. No hardware, flight, model inference or commands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from space_landing.evidence_bundle import bundle
from space_landing.synthetic import validate_dataset


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"expected JSON object in {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root: Path) -> dict:
    root = Path(root)
    required = (
        "synthetic-fixture/manifest.json",
        "synthetic-fixture/observations.jsonl",
        "synthetic-ground-truth-oracle.mot",
        "ros3-demo.jsonl",
        "ros3-evidence.json",
        "vera-evidence.json",
        "offline-bundle.json",
    )
    if not all((root / filename).is_file() for filename in required):
        raise ValueError("missing hosted upstream evidence inputs")
    if validate_dataset(root / "synthetic-fixture") != 6:
        raise ValueError("unexpected synthetic frame count")
    ros3 = _read_json(root / "ros3-evidence.json")
    vera = _read_json(root / "vera-evidence.json")
    expected_bundle = bundle(
        root / "synthetic-fixture",
        ros3_report=root / "ros3-evidence.json",
        vera_report=root / "vera-evidence.json",
    )
    saved = _read_json(root / "offline-bundle.json")
    if saved != expected_bundle:
        raise ValueError("saved bundle differs from bounded re-evaluation")
    if _sha(root / "ros3-demo.jsonl") != ros3.get("recording_sha256"):
        raise ValueError("ROS3 source-recording fingerprint mismatch")
    if _sha(root / "synthetic-ground-truth-oracle.mot") != vera.get("mot_sha256"):
        raise ValueError("VERA-MOT source-file fingerprint mismatch")
    if ros3.get("accepted", 0) < 1 or ros3.get("observed_stale_change_count", 0) < 1:
        raise ValueError("ROS3 demo did not demonstrate receiver state change")
    if vera.get("frames_with_output") != 6 or vera.get("track_observation_rows") != 6:
        raise ValueError("VERA-MOT exporter did not parse the six oracle rows")
    if saved["cross_source_alignment"] != "not_verified":
        raise ValueError("unverified clock alignment may not be promoted")
    if saved["claims"]["ardupilot_sitl_connected_here"]:
        raise ValueError("unexpected ArduPilot connection claim")

    lock_path = Path(__file__).resolve().parents[1] / "integrations" / "upstream-lock.json"
    lock = _read_json(lock_path)
    if lock.get("lock_version") != 1:
        raise ValueError("unsupported upstream lock")
    return {
        "verification_version": 1,
        "scope": "hosted_synthetic_upstream_exporter_files_only",
        "upstream_locks": {
            "ros3": lock["ros3"]["commit"],
            "vera_mot": lock["vera_mot"]["commit"],
        },
        "hashes": {
            "ros3_recording_sha256": _sha(root / "ros3-demo.jsonl"),
            "ros3_report_sha256": _sha(root / "ros3-evidence.json"),
            "vera_mot_oracle_sha256": _sha(root / "synthetic-ground-truth-oracle.mot"),
            "vera_report_sha256": _sha(root / "vera-evidence.json"),
            "bundle_sha256": _sha(root / "offline-bundle.json"),
        },
        "checks": {
            "ros3_exporter_report_matches_recording_bytes": True,
            "vera_exporter_report_matches_mot_bytes": True,
            "bundle_recomputed_equal": True,
            "clock_alignment_verified": False,
            "robot_camera_mapping_verified": False,
            "vera_model_inference_performed": False,
            "ardupilot_sitl_executed": False,
            "physical_landing_simulated": False,
        },
        "interpretation": (
            "The GitHub Actions run log records whether pinned exporter modules "
            "executed. This JSON verifies file equality and source claims only. "
            "VERA input is a synthetic ground-truth oracle, NOT model predictions."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    report = verify(args.root)
    output = args.root / "cloud-integration-receipt.json"
    output.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
