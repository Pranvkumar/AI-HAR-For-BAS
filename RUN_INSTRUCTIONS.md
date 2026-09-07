# Run Instructions

These steps run the bundled offline demo on a new Windows PC.

## 1. Install prerequisites

Install Python 3.10 or newer, then open PowerShell in this repository:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

If PowerShell blocks activation, run the commands from `cmd.exe` instead:

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e .
```

## 2. Run the offline demonstration

This needs no camera, network, or additional model download:

```powershell
python scripts/run_sih_demo.py
```

The generated video and telemetry are written under `demo-output/`.

## 3. Run the bundled models with a camera

Make sure a webcam is connected, then run:

```powershell
python scripts/run_pipeline.py --config configs/app.yaml --source 0
```

The default configuration uses `models/exported/best.pt` and
`models/gesture_recognizer.task`. It runs YOLO on CPU with the portable `auto`
backend; an optional TensorRT engine can be configured later for a compatible
NVIDIA machine.

In a second terminal, activate the environment and start the dashboard:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run src/har/outputs/gui/dashboard.py
```

Open `http://127.0.0.1:8000/stream` for the MJPEG stream.

## 4. Run tests

```powershell
python -m pytest
```

The committed model files are the complete offline inference bundle. Do not
delete `models/` when copying or cloning the project.