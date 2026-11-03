# fluids_landing_andor_surfacing

**Software-only, open-source research prototype** for synthetic landing-scene perception and observation evidence. This is **not** a flight simulator, rocket dynamics model, guidance system, or physical landing controller.

## Milestone 2: deterministic synthetic camera dataset

Requires **Python 3.10+**; the generator uses only the standard library.

```bash
python -m space_landing generate --out runs/example --frames 12 --width 160 --height 120 --fps 5 --seed 7
python -m space_landing validate runs/example
python -m unittest discover -s tests -v
```

Outputs are `manifest.json`, `observations.jsonl`, and `frames/frame_0000.png`, etc. Generation fails rather than overwriting an existing output directory. Given identical config, output file bytes are identical across runs. Virtual timestamps start at zero in nanoseconds; images and annotations are synthetic.

The JSONL observation contract is described in [schemas/observation-v1.schema.json](schemas/observation-v1.schema.json). The built-in validator checks provenance, sequence timestamps, bounding-box containment, PNG signatures and file hashes, but is not a general-purpose JSON Schema validator.

**No ArduPilot SITL, ROS3, ROS 2, or VERA-MOT integration has been exercised here yet.** Planned read-only adapters are described in [SPACE_LANDING_RESEARCH.md](SPACE_LANDING_RESEARCH.md); model training, physical flight, guidance, actuator and vehicle-control code are outside scope.

## Research milestones

- [x] Deterministic PNG scene frames, frame annotations, manifest, validation and unit tests
- [x] Versioned synthetic observation JSON schema
- [ ] Optional VERA-MOT tracking/evidence import (no claims about model performance)
- [ ] Optional ArduPilot SITL receive-only telemetry adapter
- [ ] ROS3-compatible receive-only observation/replay evaluation
- [ ] Timestamp, loss/recovery and tracking-quality benchmarks

## Reproducibility and limitations

Scenes are **abstract screen-space drawings**, not simulated planetary surface physics. The proxy's motion is an illustrative interpolation, not a vehicle trajectory. The target is not a trained detector class, and the fixtures do not validate tracking accuracy, navigation, real-time links, hardware or spaceflight.

Licensed under the Apache License 2.0 (see [LICENSE](LICENSE)).
