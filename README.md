# AEGIS AI-HAR for BAS

AEGIS is an offline, safety-aware assistant for validating astronaut payload
procedures. This repository now contains the consolidated AEGIS runtime:
MediaPipe hands, optional GPU object detection, object tracking, relational
containment evidence, temporal recognition, protocol FSM, safe modes, audit
logging, recording, voice alerts, and the live mission console.

## Project Layout

- `src/aegis/` is the maintained runtime and training integration.
- `configs/` contains the app and experiment protocol configuration.
- `datasets/objects/` is the local YOLO dataset location. Private images are
	intentionally excluded from Git.
- `tests/` contains hardware-free detector, tracking, fusion, safety, and
	protocol tests.

The older `src/har/` implementation remains for reference during migration;
new work should use `aegis`.

## Google Colab Training

Colab is useful when you want a temporary NVIDIA GPU. Upload or clone this
repository into a Colab session, then run:

```python
%cd /content/AI-HAR-For-BAS
!pip install -r requirements-train.txt
```

Upload reviewed YOLO images and labels into:

```text
datasets/objects/images/train/
datasets/objects/images/val/
datasets/objects/labels/train/
datasets/objects/labels/val/
```

Use the canonical classes in this order:
`outer_container`, `container_lid`, `red_box`, `blue_box`, `astronaut_hand`.
Then train and export on the Colab GPU:

```python
!python -m aegis.tools.train_objects split
!python -m aegis.tools.train_objects train --device auto --epochs 80 --batch 8
!python -m aegis.tools.train_objects export
!python -m aegis.tools.train_objects check
```

Download `models/objects/objects.onnx` and its `.names.json` sidecar after
training. Do not upload private webcam images to GitHub. Review every
auto-generated label before training; colour mistakes between red and blue
objects directly reduce wrong-object accuracy.

## Windows Laptop Training

The RTX 4050 laptop is usually the simplest option for repeated experiments:

```powershell
cd C:\path\to\AI-HAR-For-BAS
.\INSTALL.bat
.\TRAIN_OBJECTS.bat grab
.\TRAIN_OBJECTS.bat autolabel
# Review labels, then:
.\TRAIN_OBJECTS.bat split
.\TRAIN_OBJECTS.bat train --device auto --epochs 80
.\TRAIN_OBJECTS.bat export
.\TRAIN_OBJECTS.bat check
```

`--device auto` selects CUDA when PyTorch can see it and otherwise falls back
to CPU. Colab can be faster only when it provides an L4 or A100; free Colab
sessions may be slower or interrupted.

## Development and Tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

Tests are hardware-free and do not require a camera or trained weights. Start
the operator console with `START.bat` after installing the runtime dependencies.
