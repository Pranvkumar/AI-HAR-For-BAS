"""Train YOLOv11n on the synthetic red/blue dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("datasets/red_blue_synth/data.yaml"))
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--project", type=Path, default=Path("models/runs"))
    parser.add_argument("--name", default="red_blue_synth")
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    if not args.data.exists():
        raise FileNotFoundError(f"dataset descriptor not found: {args.data}")

    model = YOLO(args.model)
    result = model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(args.project),
        name=args.name,
        exist_ok=True,
        patience=args.patience,
        workers=args.workers,
        degrees=180,
        hsv_h=0.015,
        hsv_s=0.45,
        hsv_v=0.4,
        translate=0.08,
        scale=0.4,
        fliplr=0.5,
    )

    best = Path(result.save_dir) / "weights" / "best.pt"
    print(f"trained_weights={best}")


if __name__ == "__main__":
    main()
