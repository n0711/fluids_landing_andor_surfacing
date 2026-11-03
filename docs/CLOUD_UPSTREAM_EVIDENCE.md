# Cloud-only upstream exporter interoperability (Milestone 5a)

**Scope: executed upstream source exporters in a GitHub-hosted synthetic job.**
No local setup, physical simulator, ArduPilot SITL run, VERA trained model
inference, ROS graph, propulsion, flight control or operational landing model.

## Concrete improvement over a mocked adapter test

An offline adapter accepting sample JSON alone does not demonstrate that an
upstream project can actually produce that file. This milestone adds a separate
GitHub Actions job which:

1. Checks out exact, reviewable upstream commits from
   n0711/ROS3-Limassol and n0711/vera-mot; see
   integrations/upstream-lock.json.
2. Runs the local standard-library generator to create a **synthetic camera
   fixture**, with an exact ground-truth MOT-format oracle.
3. Runs the **actual pinned ROS3-Limassol demo and evidence exporter** under
   Python 3.12. ROS3's demo uses virtual time and its own simulated telemetry.
   This does not connect to ArduPilot, a real network, or a physical robot.
4. Runs the **actual pinned VERA-MOT vision_evidence exporter** against the
   synthetic oracle MOT text. This checks the import/export format and source
   parsing, **not model inference** or identity correctness.
5. Uses our offline evidence_bundle module to produce a JSON bundle. The
   sources remain separate and explicitly *not time-aligned*.
6. Rehashes the source ROS3 recording and source MOT text; checks each
   exported SHA-256, counts, the bundle and all non-alignment claims.
7. Uploads the fixture, source reports, independent bundle and integrity
   receipt as a 30-day GitHub Actions artifact.

All jobs run in GitHub Actions. The user does not need to execute a simulator
or install upstream repositories locally.

## Distinguishing scientific claim

The supported engineering claim, if CI passes, is **interoperability of the
pinned offline evidence exporters with strictly bounded, non-aligned
summaries**. It is not a performance result for VERA-MOT's ReID method, ROS3's
real radio-link reliability, ArduPilot's flight software, or a lunar/martian
landing system.

The real research hypothesis remains that a transport-recent packet can
contain a stale source sample, and that credible evidence must distinguish
capture freshness from receiver arrival freshness. This is presently tested
against deterministic synthetic counterfactuals, not real sensor data.

## Known limitations and provenance

- The VERA-MOT source file is a generated *oracle*: perfect overlap with its
  generator annotations is tautological and cannot be reported as a learned
  tracking-model result.
- ROS3's virtual-time demo deliberately has a synthetic communication
  blackout; it is **not** an ArduPilot SITL run or a real network outage.
- Cross-source sequence mappings, clocks, and camera origins are unknown.
  No synchronized measurements, sensor fusion, or causal consistency claims
  can be extracted from this bundle.
- The receipt hashes identify byte equality only; they are not digital
  signatures, trusted clock attestations, or proof of external source
  authenticity.
- The job only validates pinned commits and Python 3.12. Reproducibility
  beyond the pinned versions and GitHub runner environment remains to be
  independently replicated.
- Both upstream GitHub repositories remain separate and independently
  maintained; no source code is copied into this repository.

## Acceptance gate

This milestone is complete only if all four hosted CI jobs are green:
Python 3.10 and 3.12 unit tests, synthetic research evidence, and
cloud-upstream-evidence. In the last job, the actual ROS3 and VERA exporters
must execute successfully, the strict bundle must validate, and the
upstream-evidence-receipt artifact must be present.

Future work: cloud-hosted receive-only ArduPilot SITL evidence, with
independent source clocks and a documented uncertainty bound, before
making cross-source timing comparisons. That remains a different milestone.
