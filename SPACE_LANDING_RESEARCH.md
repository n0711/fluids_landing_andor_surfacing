# Space Landing Research Simulator (proposed)

This repository is an open-source, **software-only** research workspace for studying visual tracking, telemetry reliability, and reproducible synthetic landing-event datasets.

## Status
Milestone 2 contains tested deterministic synthetic PNG scenes, ground-truth observation JSONL, a versioned JSON Schema, and a local content validator. This is a **screen-space observation fixture**, not a dynamics or flight simulator. No integrated ArduPilot SITL, validated ROS graph, VERA-MOT model run, or ROS3 experiment is claimed.

## Components
- **Synthetic scene generator:** produces pre-recorded or generated camera frames and abstract landing-event annotations; no physical vehicle dynamics or propulsion model.
- **VERA-MOT adapter (read-only):** accepts synthetic frames and emits detections/tracks with timestamps, confidence and provenance.
- **ArduPilot SITL observer (read-only):** subscribes to selected telemetry from a separately managed ArduPilot SITL environment; never sends MAVLink commands.
- **ROS 2 / ROS3-Limassol observer:** records/replays bounded telemetry and perception metadata, including freshness, message loss and recovery.
- **Evaluation:** measures tracking precision/recall, timestamp alignment, dropped-frame rate, telemetry age, and replay determinism.

## Data flow
```text
Synthetic camera frames ---> VERA-MOT observer ---+
                                                   +--> ROS 2 / ROS3 observation log --> offline metrics
ArduPilot SITL telemetry --> read-only observer ---+
```

## Milestones
1. **Done:** deterministic synthetic frames, labels, manifest, and standard-library unit tests.
2. **Done:** versioned JSON observation schema with source, timestamps, frame IDs, and simulation-only provenance.
3. Build optional, read-only adapters for VERA-MOT and ArduPilot SITL, guarded by feature flags.
4. Evaluate ROS3 record/replay under synthetic message drop and delay.
5. Publish repeatable metrics and explicit limitations.

## Safety and scope
- Simulation and offline analysis only; no real-world rocket landing, flight, guidance, propulsion, ignition, actuation, or vehicle command logic.
- Do not connect this prototype to physical vehicles.
- All datasets must distinguish synthetic from field observations.
- No claims of physical, flight, or space qualification.

## Integration references
- https://ardupilot.org/dev/docs/ros2-sitl.html
- https://github.com/n0711/vera-mot
- https://github.com/n0711/ROS3-Limassol

## License
Apache License 2.0 is already present in the repository. Maintain this license for the research fixtures unless the repository owner explicitly changes it.
