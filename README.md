# AI-HAR-For-BAS

An offline edge assistant that uses computer vision to track, validate, and
provide guidance for astronaut science experiments in space. The target demo
hardware is a Lenovo Legion laptop with an RTX 4060 and NVENC; CPU fallbacks
keep development and tests possible without a GPU.

## Status

Phase 1 and Phase 2 are implemented: the project includes the Ultralytics
tracking adapter, training/export utilities, CPU MediaPipe adapter, relational
hand-object fusion, YAML protocol loading, and a fault-tolerant protocol FSM.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

Tests use synthetic events and do not download weights or require a camera.
Provide a trained `.pt` or TensorRT `.engine` path when using
`har.vision.yolo_wrapper.YoloDetector` in a live environment.

For a CPU smoke run with the COCO-pretrained YOLO11n placeholder, download
`yolo11n.pt` at build time, then use `configs/demo_cpu.yaml`. Replace that
path with the BAS-trained weights for the real experiment.

## Synthetic Dataset and Training

For the red/blue microgravity mock procedure, generate a local synthetic dataset,
train YOLOv11n, and run the full pipeline:

```bash
python scripts/build_red_blue_pipeline.py --epochs 25
PYTHONPATH=src python scripts/benchmark_pipeline.py --config configs/demo_red_blue_boxes_cpu.yaml --seconds 10
```

PowerShell:

```powershell
$env:PYTHONPATH = "src"
python scripts/build_red_blue_pipeline.py --epochs 25
python scripts/benchmark_pipeline.py --config configs/demo_red_blue_boxes_cpu.yaml --seconds 10
```

### Notes

- Synthetic images and YOLO labels are generated under `datasets/red_blue_synth/`.
- Training metrics and checkpoints are written under `runs/detect/models/runs/red_blue_synth/`.
- `best.pt` weights are git-ignored by design; regenerate locally with
	`python scripts/build_red_blue_pipeline.py --epochs 25` before running the benchmark config.
- Procedure protocol and anomaly rules are in `configs/protocol_red_blue_boxes.yaml`.
