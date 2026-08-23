"""Export a trained Ultralytics model to ONNX and optionally TensorRT."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("weights", type=Path)
    parser.add_argument("--output", type=Path, default=Path("models/exported"))
    parser.add_argument(
        "--int8", action="store_true", help="Reserved for Phase 4 calibration support"
    )
    args = parser.parse_args()
    if args.int8:
        raise NotImplementedError("INT8 calibration is planned for Phase 4")
    from ultralytics import YOLO

    model = YOLO(str(args.weights))
    args.output.mkdir(parents=True, exist_ok=True)
    model.export(format="onnx", imgsz=640, dynamic=False)
    model.export(format="engine", half=True, imgsz=640, device=0)


if __name__ == "__main__":
    main()
