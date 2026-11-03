"""Reproducible synthetic camera frames; no vehicle dynamics or actuation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import random
import struct
import zlib

SCHEMA_VERSION = "1.0.0"
SCENARIO = "visual_landing_proxy_v1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class SceneConfig:
    frames: int = 12
    width: int = 160
    height: int = 120
    fps: int = 5
    seed: int = 7

    def validate(self) -> None:
        for name, low, high in (("frames", 1, 1000), ("width", 64, 1024),
                                ("height", 64, 1024), ("fps", 1, 120),
                                ("seed", 0, 2**32 - 1)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer in [{low}, {high}]")


def _chunk(name: bytes, payload: bytes) -> bytes:
    data = name + payload
    return struct.pack(">I", len(payload)) + data + struct.pack(">I", zlib.crc32(data) & 0xFFFFFFFF)


def _png(width: int, height: int, pixels: bytearray) -> bytes:
    stride = width * 3
    data = b"".join(b"\x00" + pixels[y * stride:(y + 1) * stride]
                    for y in range(height))
    return (PNG_SIGNATURE + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(data, level=9)) + _chunk(b"IEND", b""))


def _rect(pixels: bytearray, width: int, height: int, x: int, y: int,
          w: int, h: int, color: tuple[int, int, int]) -> None:
    rgb = bytes(color)
    for row in range(max(0, y), min(height, y + h)):
        for col in range(max(0, x), min(width, x + w)):
            offset = 3 * (row * width + col)
            pixels[offset:offset + 3] = rgb


def _render(cfg: SceneConfig, index: int) -> tuple[bytes, list[int]]:
    """Draw abstract target motion, not a physical trajectory model."""
    pixels = bytearray(bytes((16, 25, 46)) * (cfg.width * cfg.height))
    randomizer = random.Random(cfg.seed)
    for _ in range(cfg.width // 2):
        sx = randomizer.randrange(cfg.width)
        sy = randomizer.randrange(cfg.height * 3 // 4)
        _rect(pixels, cfg.width, cfg.height, sx, sy, 1, 1, (125, 136, 156))
    ground_y = cfg.height * 4 // 5
    _rect(pixels, cfg.width, cfg.height, 0, ground_y, cfg.width,
          cfg.height - ground_y, (69, 74, 79))
    _rect(pixels, cfg.width, cfg.height, cfg.width * 3 // 8,
          ground_y, cfg.width // 4, 3, (210, 203, 117))
    target_w, target_h = max(8, cfg.width // 12), max(10, cfg.height // 9)
    phase = index / max(1, cfg.frames - 1)
    tx = cfg.width // 2 - target_w // 2 + round((2 - 4 * phase) * cfg.width / 80)
    ty = cfg.height // 8 + round(phase * cfg.height / 2)
    _rect(pixels, cfg.width, cfg.height, tx, ty, target_w, target_h, (233, 169, 84))
    _rect(pixels, cfg.width, cfg.height, tx + target_w // 3, ty + 2,
          max(1, target_w // 3), max(1, target_h // 3), (218, 229, 237))
    return _png(cfg.width, cfg.height, pixels), [tx, ty, target_w, target_h]


def _json_line(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n"


def generate_dataset(output: Path, cfg: SceneConfig = SceneConfig()) -> dict:
    """Create a new dataset directory; never overwrite existing files."""
    cfg.validate()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "frames").mkdir()
    lines = []
    for index in range(cfg.frames):
        image, bbox = _render(cfg, index)
        relative = f"frames/frame_{index:04d}.png"
        (output / relative).write_bytes(image)
        observation = {
            "schema_version": SCHEMA_VERSION,
            "simulation_only": True,
            "source": "synthetic_camera",
            "frame_id": f"camera-{index:04d}",
            "timestamp_ns": index * 1_000_000_000 // cfg.fps,
            "image": {"path": relative, "sha256": hashlib.sha256(image).hexdigest(),
                      "width": cfg.width, "height": cfg.height},
            "objects": [{"track_id": "visual-proxy-1", "class_label": "visual_proxy",
                         "bbox_xywh": bbox}],
            "provenance": {"origin": "synthetic", "generator": "space_landing.synthetic",
                           "seed": cfg.seed, "scenario": SCENARIO},
        }
        lines.append(_json_line(observation))
    raw = "".join(lines).encode("utf-8")
    (output / "observations.jsonl").write_bytes(raw)
    manifest = {"schema_version": SCHEMA_VERSION, "simulation_only": True,
                "scenario": SCENARIO, "config": asdict(cfg), "observations": "observations.jsonl",
                "observations_sha256": hashlib.sha256(raw).hexdigest(),
                "frame_count": cfg.frames}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _safe_relative_path(path: str) -> bool:
    pure = PurePosixPath(path)
    return (type(path) is str and not pure.is_absolute() and
            len(pure.parts) == 2 and pure.parts[0] == "frames" and
            all(part not in ("", ".", "..") for part in pure.parts) and "\\" not in path)


def validate_dataset(output: Path) -> int:
    """Verify generated fixtures and hashes; not a full JSON Schema engine."""
    base = Path(output)
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("simulation_only") is not True:
        raise ValueError("invalid manifest version or provenance")
    cfg = SceneConfig(**manifest["config"])
    cfg.validate()
    if manifest.get("scenario") != SCENARIO or manifest.get("frame_count") != cfg.frames:
        raise ValueError("invalid manifest count or scenario")
    if manifest.get("observations") != "observations.jsonl":
        raise ValueError("unexpected observation path")
    raw = (base / "observations.jsonl").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest.get("observations_sha256"):
        raise ValueError("observation hash mismatch")
    rows = raw.decode("utf-8").splitlines()
    if len(rows) != cfg.frames:
        raise ValueError("observation count mismatch")
    for index, row in enumerate(rows):
        item = json.loads(row)
        if (item.get("schema_version") != SCHEMA_VERSION or item.get("simulation_only") is not True
                or item.get("source") != "synthetic_camera"
                or item.get("frame_id") != f"camera-{index:04d}"
                or type(item.get("timestamp_ns")) is not int
                or item["timestamp_ns"] != index * 1_000_000_000 // cfg.fps
                or item.get("provenance") != {"origin": "synthetic",
                                              "generator": "space_landing.synthetic",
                                              "seed": cfg.seed, "scenario": SCENARIO}):
            raise ValueError(f"invalid observation metadata at frame {index}")
        image = item["image"]
        path = image.get("path")
        if not _safe_relative_path(path) or path != f"frames/frame_{index:04d}.png":
            raise ValueError(f"invalid image path at frame {index}")
        image_file = base / path
        if image_file.is_symlink():
            raise ValueError("symlinked image forbidden")
        data = image_file.read_bytes()
        if (not data.startswith(PNG_SIGNATURE) or
                hashlib.sha256(data).hexdigest() != image.get("sha256") or
                image.get("width") != cfg.width or image.get("height") != cfg.height):
            raise ValueError(f"image mismatch at frame {index}")
        objects = item.get("objects")
        if type(objects) is not list or len(objects) != 1:
            raise ValueError("expected one proxy object")
        obj = objects[0]
        bbox = obj.get("bbox_xywh")
        if (obj.get("track_id") != "visual-proxy-1" or obj.get("class_label") != "visual_proxy"
                or type(bbox) is not list or len(bbox) != 4
                or any(type(v) is not int for v in bbox)):
            raise ValueError("invalid proxy metadata")
        x, y, w, h = bbox
        if min(x, y) < 0 or min(w, h) < 1 or x + w > cfg.width or y + h > cfg.height:
            raise ValueError("bounding box outside image")
    return len(rows)
