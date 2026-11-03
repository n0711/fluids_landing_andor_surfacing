# Space Landing Research Simulator (proposed)

This repository is an open-source, **software-only** research workspace for studying visual tracking, telemetry reliability, and reproducible synthetic landing-event datasets.

## Status
Research scaffold only. No integrated simulator, validated ROS graph, ArduPilot SITL run, VERA-MOT model run, or ROS3 experiment is claimed.

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
1. Add deterministic synthetic frames, labels, manifest, and unit tests.
2. Define a versioned JSON observation schema with source, timestamp, frame ID, and simulation-only provenance.
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
Select an OSI-approved open-source license before accepting contributions or publishing reusable code.
