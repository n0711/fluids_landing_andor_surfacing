"""Read-only MOTChallenge-10 output evaluation against synthetic visual-proxy labels.

Accepts the text format used by VERA-MOT's MOT I/O and aggregate exporter.
Does NOT execute VERA-MOT, establish identities, or assess physical landing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from .synthetic import validate_dataset

MAX_MOT_BYTES = 8_000_000
MAX_MOT_ROWS = 100_000
MAX_LINE_BYTES = 4096
IOU_THRESHOLD = 0.5


def _iou(a: list[float], b: list[float]) -> float:
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[0] + a[2], b[0] + b[2])
    bottom = min(a[1] + a[3], b[1] + b[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = a[2] * a[3] + b[2] * b[3] - intersection
    return intersection / union if union > 0 else 0.0


def parse_mot(data: bytes, frame_count: int) -> dict[int, list[list[float]]]:
    """Bound and strictly validate pre-existing VERA-compatible tracker rows."""
    if type(data) is not bytes or not data or len(data) > MAX_MOT_BYTES:
        raise ValueError("MOT file must be nonempty, at most 8 MB")
    results: dict[int, list[list[float]]] = {}
    last = 0
    seen_ids: set[int] = set()
    lines = data.splitlines()
    if len(lines) > MAX_MOT_ROWS:
        raise ValueError("too many MOT rows")
    for index, line in enumerate(lines, 1):
        if not line or len(line) > MAX_LINE_BYTES:
            raise ValueError(f"MOT line {index}: empty or oversized row")
        try:
            fields = [float(value) for value in line.decode("utf-8").split(",")]
        except (UnicodeError, ValueError, OverflowError) as exc:
            raise ValueError(f"MOT line {index}: invalid numeric fields") from exc
        if len(fields) != 10 or not all(math.isfinite(number) for number in fields):
            raise ValueError(f"MOT line {index}: expected ten finite numbers")
        f, track_id = fields[:2]
        if (not f.is_integer() or not track_id.is_integer()
                or not 1 <= f <= frame_count or track_id < 1):
            raise ValueError(f"MOT line {index}: invalid frame/track number")
        frame = int(f)
        identity = int(track_id)
        if frame < last:
            raise ValueError(f"MOT line {index}: frame numbers must be sorted")
        if frame != last:
            seen_ids.clear()
        if identity in seen_ids:
            raise ValueError(f"MOT line {index}: duplicate identity in frame")
        seen_ids.add(identity)
        last = frame
        box = fields[2:6]
        if box[2] <= 0 or box[3] <= 0:
            raise ValueError(f"MOT line {index}: invalid box size")
        results.setdefault(frame, []).append(box)
    return results


def evaluate_mot(dataset: Path, mot_file: Path) -> dict:
    """One-to-one single-target IoU assessment; no identity/HOTA claim."""
    dataset = Path(dataset)
    validate_dataset(dataset)
    raw_obs = (dataset / "observations.jsonl").read_bytes()
    obs = [json.loads(line) for line in raw_obs.splitlines()]
    mot_bytes = Path(mot_file).read_bytes()
    pred = parse_mot(mot_bytes, len(obs))
    tp = fp = fn = 0
    matched_ious: list[float] = []
    for frame, row in enumerate(obs, 1):
        gt = row["objects"][0]["bbox_xywh"]
        boxes = pred.get(frame, [])
        # One ground-truth proxy per frame. The best IoU candidate is matched
        # once; all remaining candidates are false positives.
        best = max((_iou(gt, box) for box in boxes), default=0.0)
        if best >= IOU_THRESHOLD:
            tp += 1
            matched_ious.append(best)
            fp += len(boxes) - 1
        else:
            fn += 1
            fp += len(boxes)
    return {
        "evaluation_version": 1,
        "scope": "single_synthetic_visual_proxy_detection_only",
        "mot_format": "motchallenge-10-column",
        "input_provenance": "unverified_external_tracker_output",
        "observations_sha256": hashlib.sha256(raw_obs).hexdigest(),
        "mot_sha256": hashlib.sha256(mot_bytes).hexdigest(),
        "iou_match_threshold": IOU_THRESHOLD,
        "metrics": {
            "ground_truth_frames": len(obs),
            "frames_with_mot_output": len(pred),
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "mean_iou_matched_only": sum(matched_ious) / len(matched_ious) if matched_ious else None,
        },
        "claims": {
            "vera_mot_executed_by_this_evaluator": False,
            "reid_identity_accuracy_established": False,
            "hota_or_idf1_established": False,
            "clock_synchronization_established": False,
            "physical_vehicle_or_landing_validation": False,
        },
        "interpretation": (
            "Offline MOT-format bounding-box overlap against synthetic annotations. "
            "Tracking identities and reliability cannot be inferred from detection overlap."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("mot_file", type=Path, help="existing MOTChallenge 10-column output")
    args = parser.parse_args()
    print(json.dumps(evaluate_mot(args.dataset, args.mot_file),
                     indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
