# fluids_landing_andor_surfacing

**Software-only, open-source research prototype** for synthetic landing-scene perception and observation evidence. This is **not** a flight simulator, rocket dynamics model, guidance system, or physical landing controller.

## Milestones 2–3: deterministic camera datasets and observation integrity evidence

Requires **Python 3.10+**; the generator uses only the standard library.

```bash
python -m space_landing generate --out runs/example --frames 12 --width 160 --height 120 --fps 5 --seed 7
python -m space_landing validate runs/example
python -m unittest discover -s tests -v
```

Outputs are `manifest.json`, `observations.jsonl`, and `frames/frame_0000.png`, etc. Generation fails rather than overwriting an existing output directory. Given identical config, output file bytes are identical across runs. Virtual timestamps start at zero in nanoseconds; images and annotations are synthetic.

The JSONL observation contract is described in [schemas/observation-v1.schema.json](schemas/observation-v1.schema.json). The built-in validator checks provenance, sequence timestamps, bounding-box containment, PNG signatures and file hashes, but is not a general-purpose JSON Schema validator.

The optional MOTChallenge reader is **format-compatible** with VERA-MOT output; it has not run the VERA-MOT model. No ArduPilot SITL, ROS3, or ROS 2 runtime integration has been exercised here. Planned receive-only adapters are described in [SPACE_LANDING_RESEARCH.md](SPACE_LANDING_RESEARCH.md); model training, physical flight, guidance, actuator and vehicle-control code are outside scope.

## Automated research evidence (GitHub Actions; no local setup)

The [Synthetic evidence CI](.github/workflows/ci.yml) workflow runs Python 3.10/3.12 unit tests and rebuilds a reproducible counterfactual observation audit on a hosted GitHub runner. Successful runs publish a 30-day `observation-integrity-evidence` artifact with SHA-256 receipts and synthetic fixture data.

The [Observation Integrity research protocol](docs/OBSERVATION_INTEGRITY.md) defines **transport freshness versus source capture freshness**, frozen synthetic ablations, and the explicit limits of each claim. A receiver that continues receiving a repeated old image can be transport-recent while its source evidence is stale. This is **not** evidence that any real vehicle is unsafe or safe.

Optional offline commands for other researchers:

```bash
python -m space_landing.integrity runs/example
python -m space_landing.mot_evaluation runs/example path/to/existing-vera-compatible.mot
```

These commands only read previously generated files and never send commands to any system.

## Research milestones

- [x] Deterministic PNG scene frames, frame annotations, manifest, validation and unit tests
- [x] Versioned synthetic observation JSON schema
- [x] Offline reader/evaluator for MOTChallenge 10-column files (VERA-MOT format compatible; no actual model run)
- [ ] Optional ArduPilot SITL receive-only telemetry adapter
- [ ] ROS3-compatible receive-only observation/replay evaluation
- [x] Synthetic arrival-versus-capture freshness ablations with SHA-256 CI evidence receipts
- [ ] Real tracking-quality benchmarks against independently generated VERA-MOT model results
- [ ] Clock-aligned offline cross-source evaluation after independently verified source timestamps

## Reproducibility and limitations

Scenes are **abstract screen-space drawings**, not simulated planetary surface physics. The proxy's motion is an illustrative interpolation, not a vehicle trajectory. The target is not a trained detector class, and the fixtures do not validate tracking accuracy, navigation, real-time links, hardware or spaceflight.

Licensed under the Apache License 2.0 (see [LICENSE](LICENSE)).
