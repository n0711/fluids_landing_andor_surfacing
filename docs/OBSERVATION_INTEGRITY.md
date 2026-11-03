# Observation Integrity Benchmark — research protocol v1

**Research question.** Can a receive-only observation system detect source evidence that
is stale even though the receiver continues to get messages? This addresses a
narrow **observability** question, *not* vehicle safety or landing guidance.

## Differentiator: two kinds of freshness, not one healthy light

The benchmark separates:
- **Transport arrival freshness:** how long since the receiver observed a message;
- **Source capture freshness:** how old the sample claims to be when observed;
- **Separate telemetry receipt:** whether another channel has continued sending.

For the controlled synthetic virtual clock only:

\[
A(t) = t - t_\mathrm{last\_arrival}, \qquad
C(t) = t - t_\mathrm{last\_capture}
\]

Declare each recent when its age is at most one generated frame interval
\(\Delta t\). Define a discrepancy indicator:

\[
D(t) = \mathbf{1}[\text{synthetic telemetry recent} \land C(t) > \Delta t].
\]

A more specific fresh-arrival / stale-capture indicator is:

\[
R(t) = \mathbf{1}[\text{visual packet arrives now} \land A(t)\leq \Delta t
                    \land C(t)>\Delta t].
\]

**Important:** Capture timestamps are only trustworthy because the generator
creates both streams on one virtual clock. In real deployments, independent
capture clocks must be synchronized and bounded; otherwise source age is
**unknown**, not proven stale or fresh. Malicious or incorrectly tagged
sources can defeat source-age checks; SHA-256 receipts are not authentication.

## Frozen synthetic comparison design

Six frames, 64 x 64 pixels, 5 Hz, seed 11. This is a deterministic abstract
visual-proxy fixture, not a simulated rocket or flight trajectory.

| Counterfactual schedule | Vision arrival ticks | Transport recent ticks | Source recent ticks | Telemetry recent ticks | Telemetry/vision discrepancy | Fresh arrival / stale capture |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Nominal | 6 | 6 | 6 | 6 | 0 | 0 |
| Vision silence, ticks 2–4 | 3 | 4 | 4 | 6 | 2 | 0 |
| Replayed source frame 1, ticks 2–4 | 6 | 6 | 4 | 6 | 2 | 2 |
| Lagged capture (2-frame offset) | 6 | 6 | 2 | 6 | 4 | 4 |

These are **fixture expectations encoded in tests**, not externally measured
performance. They are not a field-detection rate or sensor-fusion accuracy
claim. The replay and silence cases have the same source-freshness discrepancy,
but different arrival freshness: that separation is the point of this milestone.

The repo's CI builds an integrity-comparison JSON report, oracle-format-check
JSON report, a source fixture and an evidence receipt with SHA-256 checksums.
Artifacts expire after 30 days in GitHub Actions; a permanent paper archive is
a later publication decision.

## VERA-MOT compatibility boundary

VERA-MOT provides MOTChallenge 10-column tracking text and the separate
vision_evidence.py aggregate exporter. The space_landing.mot_evaluation module
accepts an **existing**, ordered, bounded MOTChallenge file and scores
single-target bounding-box IoU against the synthetic fixture.

- This is offline result **format compatibility**, not a trained VERA-MOT
  detector run, association-gating integration or model validation.
- Synthetic ground truth is used as an exact **oracle** solely to assert that
  the metric and file parser behave as expected. Its perfect precision/recall
  are tautological and **must not** be advertised as VERA performance.
- The reported IoU, synthetic precision and recall are *detection* metrics,
  not identity correctness, HOTA, IDF1 or ReID reliability.
- Frame IDs are sequence-local; track IDs are never verified stable identities.

## ROS3 and ArduPilot boundaries

ROS3-Limassol receiver HEALTHY means validated telemetry has arrived recently,
not that the source observation, camera, navigation or vehicle is safe. This
benchmark illustrates why the two age dimensions should be reported
independently. It does **not** execute ROS3 or reproduce its record/replay
implementation.

ArduPilot SITL could later supply **receive-only** telemetry through an
independently managed simulator. This version uses only a labeled, synthetic
per-tick telemetry fixture. It contains **no MAVLink sender**, no control
commands, and no SITL integration.

## Reproduction through GitHub only

Repository CI automatically executes the standard-library unit tests and
builds evidence artifacts on a hosted runner for each pull request and push.
The owner does not need to run anything on their computer.

For researchers opting to reproduce locally:

~~~sh
python -m space_landing generate --out runs/observation-fixture --frames 6 --width 64 --height 64 --fps 5 --seed 11
python -m space_landing.integrity runs/observation-fixture
python -m space_landing.mot_evaluation runs/observation-fixture /path/to/existing-tracker-output.txt
python -m unittest discover -s tests -v
~~~

Never substitute generated oracle data for independent tracker evidence.

## Next controlled milestone

1. Add **offline ROS3 receiver-evidence import** with an explicit
   *unverified clock-alignment* state, preserving its source limitations.
2. Add optional **receive-only ArduPilot SITL recording import** (no command
   channel), with source IDs and independent capture/arrival timestamps.
3. Import externally generated VERA-MOT results under a frozen sequence
   mapping; compare detector overlap, tracking metrics and freshness without
   claiming any cross-modal identity match unless established independently.
4. Conduct ablations: arrival-only vs capture-age-aware, known source-age
   vs untrusted source timestamps, and missing-frame vs repeated-frame
   scenarios. Pre-register thresholds before reporting findings.

No flight software, hardware, propulsion, ignition, vehicle control or
operational landing capability is within this research milestone.
