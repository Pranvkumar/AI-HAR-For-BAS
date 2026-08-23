"""Export a trained Ultralytics model to ONNX and optionally TensorRT."""

import argparse
import importlib
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("weights", type=Path)
    parser.add_argument("--output", type=Path, default=Path("models/exported"))
    parser.add_argument(
        "--int8", action="store_true", help="Build an INT8 engine"
    )
    parser.add_argument("--calibration-data", type=Path, help="Calibration data.yaml for INT8 export")
    args = parser.parse_args()
    if args.int8 and args.calibration_data is None:
        parser.error("--calibration-data is required with --int8")
    YOLO = importlib.import_module("ultralytics").YOLO

    model = YOLO(str(args.weights))
    args.output.mkdir(parents=True, exist_ok=True)
    model.export(format="onnx", imgsz=640, dynamic=False)
    options = {"format": "engine", "imgsz": 640, "device": 0, "int8": args.int8}
    if args.int8:
        options["data"] = str(args.calibration_data)
    else:
        options["half"] = True
    model.export(**options)


if __name__ == "__main__":
    main()
