# AEGIS AI-HAR for BAS

AEGIS is an offline, safety-aware assistant for validating astronaut payload
procedures. This repository now contains the consolidated AEGIS runtime:
MediaPipe hands, optional GPU object detection, object tracking, relational
containment evidence, temporal recognition, protocol FSM, safe modes, audit
logging, recording, voice alerts, and the live mission console.

## Quick Start

From PowerShell:

```powershell
cd C:\SIH\AI-HAR-For-BAS
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m aegis.gui.app
```

Or double-click `START.bat` in the repository folder. To run silently without
voice instructions or voice alerts:

```powershell
.venv\Scripts\python.exe -m aegis.gui.app --no-voice
```

You can also start silently with the launcher:

```powershell
START.bat --no-voice
```

To disable voice by default, set this in `configs/app.yaml`:

```yaml
voice_enabled: false
```

Run diagnostics with:

```powershell
.venv\Scripts\python.exe -m aegis.tools.diagnostics
```

Run tests with:

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m pytest -q
```

## Project Layout

- `src/aegis/` is the maintained runtime and training integration.
- `configs/` contains the app and experiment protocol configuration.
- `datasets/objects/` is the local YOLO dataset location. Private images are
	intentionally excluded from Git.
- `tests/` contains hardware-free detector, tracking, fusion, safety, and
	protocol tests.

The older `src/har/` implementation remains for reference during migration;
new work should use `aegis`.

## Training

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
to CPU.

## Development and Tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

Tests are hardware-free and do not require a camera or trained weights. Start
the operator console with `START.bat` after installing the runtime dependencies.
