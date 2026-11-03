# Offline multisource evidence — ROS3-Limassol + VERA-MOT + synthetic landing observations

**Status: implemented input-format adapters and tests; no real cross-repository
runtime execution or clock alignment established.**

## Purpose

Enable a reproducible **evidence ledger** for space-analog observation research:
a synthetic screen-space scene, a ROS3-Limassol receiver-summary report and a
VERA-MOT aggregate tracker-summary report can be placed side by side without
pretending they were measured by synchronized sensors.

This deliberately does not infer a rocket's position, safety, trajectory,
landing outcome, or control decisions.

## Three different evidence domains

| Domain | What its source says | What it does not establish |
| --- | --- | --- |
| Synthetic landing fixture | Frame hashes, labels, virtual timestamps, captured vs received sample ages | Actual sensor latency, real terrain, flight dynamics |
| ROS3-Limassol evidence v1 | Receiver-observed accepted/rejected telemetry, silent observation ticks, observed stale/recovery transitions | Sent packet counts, delivery ratio, source clock, capture age, real vehicle state |
| VERA-MOT vision report v1 | Existing MOTChallenge output row counts, frames with tracker output, sequence-local IDs | Verified tracking identity, camera frame timestamps, HOTA/IDF1, model inference |

The ROS3 upstream report is produced by its evidence exporter. The VERA
upstream report is produced by its bounded vision_evidence exporter. Our
adapter validates their reported fields and counters, then records the raw
report-byte SHA-256 as provenance for later independent inspection.

**Source report hashes are not authenticated provenance** and we do not have
the original ROS3 recording or MOT file to independently verify their
contents. This limitation is encoded in the output field names.

## The key research design: explicit UNVERIFIED alignment

The evidence bundle contains:
- A single-clock synthetic counterfactual audit with reproducible frame-age
  discrepancies;
- An optional ROS3 receiver-domain summary, preserving its own timeout;
- An optional VERA sequence-domain summary;
- An explicit cross_source_alignment = not_verified marker;
- An explicit robot_to_camera_sequence_mapping = not_verified marker;
- A claims block with every physical, inference and synchronization claim false.

**Do not correlate synthetic frame times with ROS3 receiver times.** They are
not aligned, even if their numeric timestamps appear similar. Likewise, a
VERA sequence label does not establish that its frames came from the same
camera, robot, or experiment as a ROS3 log.

## Compatible offline use, for independent researchers

Previously generated source reports may be supplied as separate JSON files:

~~~sh
python -m space_landing.evidence_bundle runs/observation-fixture \
  --scenario replayed_frame \
  --ros3 previously-exported-ros3-evidence.json \
  --vera previously-exported-vera-vision-evidence.json
~~~

One or both external reports may be omitted, but at least one is required.
This command only reads existing files and prints a JSON summary. It cannot
connect to MAVLink, launch a ROS process, send commands or operate a vehicle.
The repository owner does **not** need to execute this locally: GitHub Actions
runs the parser/unit tests on hosted infrastructure.

For upstream data format documentation:
- ROS3-Limassol: robotics/ros3_limassol/docs/EVIDENCE.md and its evidence.py.
- VERA-MOT: src/vera_mot/vision_evidence.py and
  docs/ROS3_VLM_INTEGRATION.md.

## Scientific value and limits

The engineering contribution is **claim-limited observability**: preserve
independent evidence without silently elevating link freshness or tracker
counts into camera freshness, identity reliability, or vehicle health.

Unlike dashboards that merge different feeds into a single health flag,
the bundle carries explicit unverified mappings. This is a testable design
choice, **not an established novel research result**. A publication would
need independent capture clock characterization, source-run provenance,
repeatable comparisons against simple baselines, and additional studies.

An eventual receive-only ArduPilot SITL observer would be a separately
validated input source. This milestone includes no SITL execution, no
physical vehicle evidence, no real-time source fusion and no field testing.
