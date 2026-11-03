"""Counterfactual receiver-observation audit using synthetic timestamps only.

No physical landing model, ROS graph, ArduPilot command, telemetry stream, or
vehicle-state inference. Transport freshness is not sensor capture freshness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .synthetic import validate_dataset

SCENARIOS = ("nominal", "vision_silence", "replayed_frame", "lagged_capture")
REPORT_VERSION = 1


def _observations(directory: Path) -> list[dict]:
    validate_dataset(directory)
    path = Path(directory) / "observations.jsonl"
    return [json.loads(row) for row in path.read_text(encoding="utf-8").splitlines()]


def _selection(tick: int, count: int, scenario: str) -> int | None:
    """Select synthetic source-frame index, never control/trajectory output."""
    if scenario == "vision_silence" and 2 <= tick < min(count, 5):
        return None
    if scenario == "replayed_frame" and 2 <= tick < min(count, 5):
        return 1
    if scenario == "lagged_capture" and tick >= 2:
        return tick - 2
    return tick


def audit(directory: Path, scenario: str) -> dict:
    """Evaluate orthogonal receiver arrival, capture age, and telemetry fixture.

    All streams use the SAME synthetic virtual clock. A real pipeline needs
    independently characterized clock synchronization and source provenance.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown synthetic scenario: {scenario}")
    directory = Path(directory)
    rows = _observations(directory)
    if len(rows) < 2:
        raise ValueError("integrity audit requires at least two frames")
    times = [row["timestamp_ns"] for row in rows]
    step_ns = times[1] - times[0]
    if step_ns <= 0 or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("observation time must strictly increase")
    # Reference time is the source fixture itself, not the host wall clock.
    # Tolerance = one nominal source interval. No safety implication.
    threshold_ns = step_ns
    last_arrival_ns: int | None = None
    last_capture_ns: int | None = None
    ledger: list[dict] = []
    for tick, now_ns in enumerate(times):
        selected = _selection(tick, len(rows), scenario)
        if selected is not None:
            capture_ns = times[selected]
            if capture_ns > now_ns:
                raise ValueError("future source timestamp")
            last_capture_ns = capture_ns
            last_arrival_ns = now_ns
        transport_age = None if last_arrival_ns is None else now_ns - last_arrival_ns
        capture_age = None if last_capture_ns is None else now_ns - last_capture_ns
        transport_recent = transport_age is not None and transport_age <= threshold_ns
        capture_recent = capture_age is not None and capture_age <= threshold_ns
        # Synthetic independent heartbeat deliberately stays recent in every
        # scenario. It is NOT an ArduPilot output nor a real-link observation.
        telemetry_recent = True
        ledger.append({
            "tick": tick,
            "virtual_time_ns": now_ns,
            "received_source_frame": selected,
            "vision_arrival_present": selected is not None,
            "vision_transport_recent": transport_recent,
            "vision_capture_recent": capture_recent,
            "synthetic_telemetry_recent": telemetry_recent,
            "telemetry_vs_vision_divergence": telemetry_recent and not capture_recent,
            "fresh_arrival_stale_capture": selected is not None and transport_recent and not capture_recent,
            "capture_age_ns": capture_age,
            "arrival_age_ns": transport_age,
        })
    original = (directory / "observations.jsonl").read_bytes()
    metrics = {
        "ticks": len(ledger),
        "vision_arrival_ticks": sum(row["vision_arrival_present"] for row in ledger),
        "transport_recent_ticks": sum(row["vision_transport_recent"] for row in ledger),
        "capture_recent_ticks": sum(row["vision_capture_recent"] for row in ledger),
        "telemetry_recent_ticks": sum(row["synthetic_telemetry_recent"] for row in ledger),
        "telemetry_vs_vision_divergence_ticks": sum(row["telemetry_vs_vision_divergence"] for row in ledger),
        "fresh_arrival_stale_capture_ticks": sum(row["fresh_arrival_stale_capture"] for row in ledger),
    }
    return {
        "report_version": REPORT_VERSION,
        "scenario": scenario,
        "scope": "synthetic_offline_receiver_observability_only",
        "inputs": {"observations_sha256": hashlib.sha256(original).hexdigest(),
                   "frame_count": len(rows)},
        "freshness_threshold_ns": threshold_ns,
        "metrics": metrics,
        "ledger": ledger,
        "claims": {
            "ardupilot_connected": False,
            "vera_mot_model_executed": False,
            "ros3_adapter_executed": False,
            "real_link_reliability": False,
            "clock_synchronization_validated": False,
            "vehicle_safety_or_landing_success": False,
        },
        "interpretation": (
            "Synthetic receiver-arrival freshness and source-capture freshness are "
            "different observability dimensions. The reference telemetry heartbeat "
            "is synthetic and cannot establish ArduPilot, ROS3, or vehicle safety."
        ),
    }


def compare_scenarios(directory: Path) -> dict:
    """Use exactly the same input dataset for all counterfactual schedules."""
    reports = [audit(directory, scenario) for scenario in SCENARIOS]
    hashes = {report["inputs"]["observations_sha256"] for report in reports}
    if len(hashes) != 1:
        raise AssertionError("counterfactual scenarios used different source records")
    return {
        "comparison_version": REPORT_VERSION,
        "scope": "synthetic_counterfactual_observation_audit",
        "observations_sha256": hashes.pop(),
        "scenarios": [{"scenario": report["scenario"], **report["metrics"]} for report in reports],
        "note": "No physical performance, flight control, or field validation is measured.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--scenario", choices=SCENARIOS)
    args = parser.parse_args()
    report = audit(args.dataset, args.scenario) if args.scenario else compare_scenarios(args.dataset)
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
