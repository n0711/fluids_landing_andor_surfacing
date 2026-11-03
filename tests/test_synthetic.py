"""CPU-only, standard-library tests. No SITL, ROS, model weights or network."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from space_landing.synthetic import SceneConfig, generate_dataset, validate_dataset, PNG_SIGNATURE


class SyntheticDatasetTests(unittest.TestCase):
    def test_deterministic_across_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            generate_dataset(a, SceneConfig(frames=4, width=64, height=64, seed=12))
            generate_dataset(b, SceneConfig(frames=4, width=64, height=64, seed=12))
            files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
            self.assertEqual(files_a, sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file()))
            for path in files_a:
                self.assertEqual((a / path).read_bytes(), (b / path).read_bytes())
            self.assertEqual(validate_dataset(a), 4)

    def test_png_and_timestamp_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data"
            generate_dataset(target, SceneConfig(frames=3, fps=3))
            observations = [json.loads(x) for x in (target / "observations.jsonl").read_text().splitlines()]
            self.assertEqual([o["timestamp_ns"] for o in observations], [0, 333333333, 666666666])
            for obs in observations:
                self.assertTrue(obs["simulation_only"])
                self.assertEqual(obs["provenance"]["origin"], "synthetic")
                self.assertTrue((target / obs["image"]["path"]).read_bytes().startswith(PNG_SIGNATURE))

    def test_reject_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data"
            generate_dataset(target, SceneConfig(frames=1))
            with self.assertRaises(FileExistsError):
                generate_dataset(target, SceneConfig(frames=1))

    def test_reject_invalid_config(self):
        for cfg in (SceneConfig(frames=0), SceneConfig(width=20), SceneConfig(fps=0),
                    SceneConfig(seed=-1), SceneConfig(frames=True)):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                cfg.validate()

    def test_reject_tampered_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data"
            generate_dataset(target, SceneConfig(frames=2))
            image = target / "frames" / "frame_0001.png"
            image.write_bytes(image.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "image mismatch"):
                validate_dataset(target)

    def test_reject_tampered_annotations_even_with_hash_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data"
            generate_dataset(target, SceneConfig(frames=2))
            file = target / "observations.jsonl"
            rows = [json.loads(x) for x in file.read_text().splitlines()]
            rows[1]["objects"][0]["bbox_xywh"] = [0, 0, 9999, 9999]
            raw = "".join(json.dumps(x, sort_keys=True, separators=(",", ":")) + "\n" for x in rows).encode()
            file.write_bytes(raw)
            manifest_file = target / "manifest.json"
            manifest = json.loads(manifest_file.read_text())
            manifest["observations_sha256"] = hashlib.sha256(raw).hexdigest()
            manifest_file.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "bounding box"):
                validate_dataset(target)

    def test_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parent.parent
            data = Path(tmp) / "example"
            result = subprocess.run([sys.executable, "-m", "space_landing", "generate", "--out", str(data),
                                     "--frames", "2", "--seed", "4"], cwd=root,
                                    check=True, capture_output=True, text=True)
            self.assertIn("Generated 2", result.stdout)
            result = subprocess.run([sys.executable, "-m", "space_landing", "validate", str(data)],
                                    cwd=root, check=True, capture_output=True, text=True)
            self.assertIn("Validated 2", result.stdout)


if __name__ == "__main__":
    unittest.main()
