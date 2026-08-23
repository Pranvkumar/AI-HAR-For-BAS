"""Export a local trained YOLO model to ONNX and TensorRT FP16."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export local best.pt weights without cloud access.")
    parser.add_argument("weights", type=Path, help="Local trained best.pt file")
    parser.add_argument("--output-dir", type=Path, default=Path("models/exported"))
    parser.add_argument("--int8", action="store_true", help="Build an INT8 engine using local calibration data")
    parser.add_argument("--calibration-data", type=Path, help="Local Ultralytics data.yaml for INT8 calibration")
    args = parser.parse_args()
    if args.int8 and (args.calibration_data is None or not args.calibration_data.is_file()):
        parser.error("--int8 requires --calibration-data pointing to a local data.yaml")
    if not args.weights.is_file():
        raise FileNotFoundError(args.weights)
    from ultralytics import YOLO

    args.output_dir.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(args.weights))
    onnx_path = Path(model.export(format="onnx", dynamic=False, simplify=True))
    target_onnx = args.output_dir / f"{args.weights.stem}.onnx"
    shutil.copy2(onnx_path, target_onnx)
    trtexec = shutil.which("trtexec")
    engine_path = args.output_dir / f"{args.weights.stem}.engine"
    if trtexec and not args.int8:
        subprocess.run([trtexec, f"--onnx={target_onnx}", f"--saveEngine={engine_path}", "--fp16"], check=True)
    else:
        exported = Path(model.export(format="engine", half=not args.int8, int8=args.int8, data=str(args.calibration_data) if args.int8 else None))
        shutil.copy2(exported, engine_path)
    print(f"ONNX: {target_onnx}\nTensorRT engine: {engine_path}")


if __name__ == "__main__":
    main()
