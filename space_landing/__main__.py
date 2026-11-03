"""CLI for generating and validating deterministic synthetic visual datasets."""

import argparse
from pathlib import Path
from .synthetic import SceneConfig, generate_dataset, validate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Software-only synthetic landing observation dataset")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("generate", help="Generate a fresh labeled dataset")
    create.add_argument("--out", required=True, type=Path)
    create.add_argument("--frames", type=int, default=12)
    create.add_argument("--width", type=int, default=160)
    create.add_argument("--height", type=int, default=120)
    create.add_argument("--fps", type=int, default=5)
    create.add_argument("--seed", type=int, default=7)
    check = sub.add_parser("validate", help="Check deterministic dataset content and hashes")
    check.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "generate":
        cfg = SceneConfig(args.frames, args.width, args.height, args.fps, args.seed)
        result = generate_dataset(args.out, cfg)
        print(f"Generated {result['frame_count']} synthetic frames in {args.out}")
    else:
        print(f"Validated {validate_dataset(args.directory)} synthetic frames")


if __name__ == "__main__":
    main()
