"""Evaluate available AEGIS models and write reproducible metric reports.

Colab example:
    !pip install -r requirements-train.txt
    !python scripts/evaluate_models.py \
        --data datasets/red_blue_synth/data.yaml \
        --models models/objects/objects.onnx models/exported/best.pt \
        --device 0

Only supervised detector metrics are computed automatically. Gesture, voice,
and action models need task-specific labeled evaluation data and are reported
as unavailable unless a dedicated evaluator is added.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _jsonable(value: Any) -> Any:
    """Convert Ultralytics and NumPy values into JSON-compatible values."""
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def discover_models(root: str | Path = ".") -> list[Path]:
    """Return model artifacts under a repository root, excluding environments."""
    root = Path(root)
    patterns = ("*.pt", "*.onnx", "*.task", "*.bin")
    paths = {
        path
        for pattern in patterns
        for path in root.rglob(pattern)
        if ".venv" not in path.parts and "runs" not in path.parts
    }
    return sorted(paths)


def describe_model(model_path: str | Path) -> dict[str, Any]:
    """Describe one artifact without requiring its task-specific evaluator."""
    path = Path(model_path)
    result: dict[str, Any] = {
        "model": str(path),
        "format": path.suffix.lower().lstrip("."),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "status": "present" if path.exists() else "missing",
    }
    if not path.exists():
        return result
    if path.suffix.lower() == ".onnx":
        try:
            import onnxruntime as ort

            session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
            metadata = session.get_modelmeta().custom_metadata_map
            result.update(
                {
                    "inputs": [_jsonable((item.name, item.shape, item.type)) for item in session.get_inputs()],
                    "outputs": [_jsonable((item.name, item.shape, item.type)) for item in session.get_outputs()],
                    "metadata": metadata,
                }
            )
        except Exception as error:
            result["metadata_error"] = str(error)
    return result


def evaluate_yolo_model(
    model_path: str | Path,
    data_path: str | Path,
    *,
    imgsz: int = 640,
    batch: int = 16,
    device: str = "0",
    split: str = "test",
    workers: int = 2,
) -> dict[str, Any]:
    """Evaluate one YOLO detector and return its metrics as a plain dict."""
    from ultralytics import YOLO

    model_path = Path(model_path)
    data_path = Path(data_path)
    if not model_path.exists():
        raise FileNotFoundError(f"model not found: {model_path}")
    if not data_path.exists():
        raise FileNotFoundError(f"dataset YAML not found: {data_path}")

    model = YOLO(str(model_path))
    validation = model.val(
        data=str(data_path),
        imgsz=imgsz,
        batch=batch,
        device=device,
        split=split,
        workers=workers,
        plots=False,
        verbose=False,
    )
    metrics = _jsonable(getattr(validation, "results_dict", {}))
    return {
        "model": str(model_path),
        "task": getattr(model, "task", "detect"),
        "classes": _jsonable(getattr(model, "names", {})),
        "data": str(data_path),
        "split": split,
        "imgsz": imgsz,
        "batch": batch,
        "device": device,
        "metrics": metrics,
        "speed_ms": _jsonable(getattr(validation, "speed", {})),
    }


def build_report(
    model_paths: list[str],
    data_path: str,
    *,
    imgsz: int,
    batch: int,
    device: str,
    split: str,
    workers: int,
    inventory: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate detector files and describe models without automatic metrics."""
    report: dict[str, Any] = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "inventory": [describe_model(path) for path in (inventory or [])],
        "evaluated_detectors": [],
        "not_evaluated": [],
    }
    for model_path in model_paths:
        try:
            report["evaluated_detectors"].append(
                evaluate_yolo_model(
                    model_path,
                    data_path,
                    imgsz=imgsz,
                    batch=batch,
                    device=device,
                    split=split,
                    workers=workers,
                )
            )
        except Exception as error:  # Keep other model evaluations running.
            report["evaluated_detectors"].append(
                {"model": model_path, "status": "error", "error": str(error)}
            )
    evaluated = {item["model"] for item in report["evaluated_detectors"]}
    for item in report["inventory"]:
        if item["model"] not in evaluated:
            report["not_evaluated"].append(
                {
                    "model": item["model"],
                    "reason": "Requires a task-specific labeled evaluation dataset.",
                }
            )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="datasets/red_blue_synth/data.yaml")
    parser.add_argument("--all", action="store_true", help="Discover every model artifact under the repository.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["models/objects/objects.onnx"],
        help="YOLO .pt or .onnx files to validate.",
    )
    parser.add_argument("--output", default="outputs/model_metrics.json")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0", help="0 for Colab GPU, cpu for CPU.")
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    model_paths = discover_models(".") if args.all else args.models
    report = build_report(
        model_paths,
        args.data,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        split=args.split,
        workers=args.workers,
        inventory=model_paths,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serializable_report = _jsonable(report)
    output_path.write_text(json.dumps(serializable_report, indent=2), encoding="utf-8")
    print(json.dumps(serializable_report, indent=2))
    print(f"report_written={output_path}")


if __name__ == "__main__":
    main()
