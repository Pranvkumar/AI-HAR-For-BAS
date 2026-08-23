"""Generate synthetic data and train a detector in one command."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("datasets/red_blue_synth"))
    parser.add_argument("--train", type=int, default=480)
    parser.add_argument("--val", type=int, default=120)
    parser.add_argument("--test", type=int, default=80)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    python = sys.executable
    run(
        [
            python,
            "scripts/generate_synthetic_red_blue_dataset.py",
            "--output",
            str(args.dataset),
            "--train",
            str(args.train),
            "--val",
            str(args.val),
            "--test",
            str(args.test),
        ]
    )
    run(
        [
            python,
            "scripts/train_red_blue_detector.py",
            "--data",
            str(args.dataset / "data.yaml"),
            "--epochs",
            str(args.epochs),
            "--imgsz",
            str(args.imgsz),
            "--batch",
            str(args.batch),
            "--device",
            str(args.device),
        ]
    )


if __name__ == "__main__":
    main()
