"""Read-only cross-repository evidence bundle with explicit non-alignment.

Imports previously exported ROS3-Limassol evidence-v1 and VERA-MOT aggregate
vision-v1 reports. No network, ROS graph, MAVLink, tracking inference or vehicle
command path. Reports are independent, not synchronized sensor fusion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from .integrity import audit, SCENARIOS

MAX_REPORT_BYTES = 1_000_000
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SEQUENCE = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    output = {}
    for name, value in pairs:
        if name in output:
            raise ValueError("duplicate JSON key: " + name)
        output[name] = value
    return output


def _no_constant(value: str):
    raise ValueError("non-finite JSON token: " + value)


def _load(path: Path) -> tuple[dict, str]:
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_REPORT_BYTES + 1)
    if not raw or len(raw) > MAX_REPORT_BYTES:
        raise ValueError("evidence report empty or exceeds 1 MB")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys,
                         parse_constant=_no_constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid UTF-8 JSON report") from exc
    if type(obj) is not dict:
        raise ValueError("evidence report must be a JSON object")
    return obj, hashlib.sha256(raw).hexdigest()


def _integer(obj: dict, name: str, *, minimum: int = 0) -> int:
    value = obj.get(name)
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _number(obj: dict, name: str, *, strictly_positive: bool = False) -> float:
    value = obj.get(name)
    if type(value) not in (float, int):
        raise ValueError(f"{name} must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be a finite number")
    if value < 0 or (strictly_positive and value == 0):
        raise ValueError(f"{name} must be positive or nonnegative as required")
    return float(value)


def _hash(obj: dict, key: str) -> str:
    value = obj.get(key)
    if type(value) is not str or not SHA256.fullmatch(value):
        raise ValueError(f"invalid SHA-256: {key}")
    return value


def _ros3_summary(report: dict, report_sha: str) -> dict:
    if type(report.get("report_version")) is not int or report["report_version"] != 1:
        raise ValueError("expected ROS3 evidence report v1")
    if report.get("recording_parsed_to_eof") is not True:
        raise ValueError("ROS3 recording not confirmed parsed to EOF")
    source_sha = _hash(report, "recording_sha256")
    robot_id = report.get("robot_id")
    if not isinstance(robot_id, str) or not 1 <= len(robot_id) <= 32:
        raise ValueError("invalid ROS3 robot_id")
    stale_after = _number(report, "stale_after_s", strictly_positive=True)
    total = _integer(report, "observation_count")
    payload = _integer(report, "payload_observation_count")
    silence = _integer(report, "silence_tick_count")
    accepted = _integer(report, "accepted")
    rejected = _integer(report, "rejected")
    stale_changes = _integer(report, "observed_stale_change_count")
    state_changes = _integer(report, "observed_state_change_count")
    recoveries = _integer(report, "observed_stale_to_healthy_recoveries")
    if (total != payload + silence or payload != accepted + rejected
            or stale_changes > state_changes or recoveries > stale_changes):
        raise ValueError("inconsistent ROS3 receiver counters")
    state = report.get("final_state")
    if state not in ("WAITING", "HEALTHY", "STALE"):
        raise ValueError("invalid ROS3 final receiver state")
    return {
        "source": "ros3-limassol",
        "report_version": 1,
        "report_sha256": report_sha,
        "source_recording_sha256_unverified": source_sha,
        "robot_id_unmapped": robot_id,
        "receiver_timeout_s": stale_after,
        "receiver_state_at_last_observed_tick": state,
        "observations": total,
        "payload_observations": payload,
        "silence_ticks": silence,
        "accepted_receiver_payloads": accepted,
        "rejected_receiver_payloads": rejected,
        "observed_stale_transitions": stale_changes,
        "observed_recoveries": recoveries,
        "clock_domain": "ROS3_receiver_relative_unmapped",
        "interpretation": (
            "Upstream ROS3 counts are receiver observations, not packet delivery, "
            "sensor capture freshness, clock synchronization or flight health."
        ),
    }


def _vera_summary(report: dict, report_sha: str) -> dict:
    if type(report.get("vision_report_version")) is not int or report["vision_report_version"] != 1:
        raise ValueError("expected VERA-MOT aggregate report v1")
    if (report.get("source") != "vera-mot" or
            report.get("source_format") != "motchallenge-10-column" or
            report.get("parsed_to_eof") is not True):
        raise ValueError("invalid or incomplete VERA-MOT evidence report")
    sequence = report.get("sequence")
    if not isinstance(sequence, str) or not SEQUENCE.fullmatch(sequence):
        raise ValueError("invalid VERA sequence")
    source_sha = _hash(report, "mot_sha256")
    rows = _integer(report, "track_observation_rows", minimum=1)
    frames = _integer(report, "frames_with_output", minimum=1)
    identities = _integer(report, "distinct_sequence_local_track_ids", minimum=1)
    first = _integer(report, "first_output_frame", minimum=1)
    last = _integer(report, "last_output_frame", minimum=1)
    mean_rows = _number(report, "mean_rows_per_output_frame", strictly_positive=True)
    if (frames > rows or identities > rows or first > last
            or frames > last - first + 1
            or not math.isclose(mean_rows, rows / frames, rel_tol=1e-9)):
        raise ValueError("inconsistent VERA-MOT aggregate counters")
    return {
        "source": "vera-mot",
        "report_version": 1,
        "report_sha256": report_sha,
        "source_mot_sha256_unverified": source_sha,
        "sequence_unmapped": sequence,
        "rows_with_tracker_output": rows,
        "frames_with_tracker_output": frames,
        "distinct_unverified_sequence_local_ids": identities,
        "first_output_frame": first,
        "last_output_frame": last,
        "clock_domain": "sequence_local_frame_numbers_only",
        "interpretation": (
            "Upstream VERA-MOT aggregate describes tracker output, not verified "
            "identity accuracy, capture time, image freshness or model performance."
        ),
    }


def bundle(dataset: Path, *, scenario: str = "replayed_frame",
           ros3_report: Path | None = None,
           vera_report: Path | None = None) -> dict:
    """Join separate summaries without any temporal or semantic fusion."""
    if ros3_report is None and vera_report is None:
        raise ValueError("supply at least one independent external evidence report")
    if scenario not in SCENARIOS:
        raise ValueError("unsupported synthetic scenario")
    synthetic = audit(dataset, scenario)
    ros3 = None
    vera = None
    if ros3_report is not None:
        obj, digest = _load(ros3_report)
        ros3 = _ros3_summary(obj, digest)
    if vera_report is not None:
        obj, digest = _load(vera_report)
        vera = _vera_summary(obj, digest)
    return {
        "bundle_version": 1,
        "scope": "offline_independent_evidence_ledger",
        "synthetic_fixture": {
            "scenario": scenario,
            "observations_sha256": synthetic["inputs"]["observations_sha256"],
            "metrics": synthetic["metrics"],
            "clock_domain": "single_synthetic_virtual_clock",
        },
        "ros3_receiver_evidence": ros3,
        "vera_mot_tracker_evidence": vera,
        "cross_source_alignment": "not_verified",
        "robot_to_camera_sequence_mapping": "not_verified",
        "capture_clock_trust": "synthetic_fixture_only",
        "claims": {
            "reports_authenticated": False,
            "vera_model_executed_here": False,
            "ros3_executed_here": False,
            "ardupilot_sitl_connected_here": False,
            "cross_source_causal_agreement_established": False,
            "source_capture_age_established_for_external_reports": False,
            "navigation_or_landing_authority": False,
        },
        "interpretation": (
            "Separate source-report summaries appear alongside a synthetic "
            "counterfactual benchmark. Their clocks, IDs, images, and causes "
            "are not matched. Do not infer cross-modal coherence or safety."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("synthetic_dataset", type=Path)
    parser.add_argument("--scenario", choices=SCENARIOS, default="replayed_frame")
    parser.add_argument("--ros3", type=Path, help="previously exported ROS3 evidence-v1 JSON")
    parser.add_argument("--vera", type=Path, help="previously exported VERA-MOT aggregate-v1 JSON")
    args = parser.parse_args()
    report = bundle(args.synthetic_dataset, scenario=args.scenario,
                    ros3_report=args.ros3, vera_report=args.vera)
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
