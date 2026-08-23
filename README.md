# AI HAR for Astronaut BAS Experiments

This repository is the starting point for an offline Human Activity Recognition system that will support astronauts carrying out scientific procedures in microgravity. A local camera will eventually provide visual evidence of procedure steps; the system will guide, alert, record, and display results locally.

## Hardware target

The demonstration target is a Lenovo Legion laptop with an NVIDIA RTX 4060, 8 GB of VRAM, and NVENC. The design will remain portable to future space-grade edge hardware and must function offline.

## Project orientation

The `src/har/` package is organized around ingestion, vision, hand-object fusion, protocol state management, configuration, and independent output sinks. The YAML files in `configs/` contain the deployment defaults and must be customized with the approved experiment procedure and local model path.

## Tests

Create a Python 3.10+ virtual environment, install the project dependencies, then run the test suite:

```bash
pip install -e .
pytest
```

## Local run

Place approved, locally trained weights at the path configured in `configs/app.yaml`. The pipeline never downloads a model. Then run:

```bash
python -m har.pipeline --config configs/app.yaml --source path/to/local-video.mp4
```

It records an annotated MP4, writes JSON Lines telemetry, and serves an MJPEG stream at `http://127.0.0.1:8000/stream`. In a second terminal, start the local dashboard:

```bash
streamlit run src/har/outputs/gui/dashboard.py
```

## Immediate offline demo

Run the complete local output and protocol path without a camera, model weights, or
network access:

```bash
python -m har.demo
```

This creates `demo-output/har-demo.mp4` and a JSONL telemetry file using a clearly
labelled synthetic protocol. It is a technical demonstration only, not an approved
astronaut procedure.

## ByteTrack smoke test

The vision layer uses Ultralytics' built-in ByteTrack support. Test it with a
local stock YOLO model and a local video file:

```bash
python scripts/run_bytetrack.py --model path/to/yolo11n.pt --source path/to/video.mp4
```

This writes `recordings/bytetrack/tracked.mp4` with object IDs. A stock model
validates tracking only; it cannot recognize the project-specific vial, pipette,
rack, centrifuge slot, or lid until the custom model is trained.

## Hand gesture recognition

For robust, detailed hand input, this project also supports MediaPipe Gesture
Recognizer alongside YOLO/ByteTrack. It recognizes `Closed_Fist`, `Open_Palm`,
`Pointing_Up`, `Thumb_Down`, `Thumb_Up`, `Victory`, and `ILoveYou`, and provides
21 landmarks per hand. Download its official model once during setup:

```bash
python -m pip install mediapipe
python scripts/download_gesture_model.py
python scripts/run_gesture_demo.py --source 0
```

The downloaded model is kept out of Git and inference runs locally afterwards.
Use the landmark information for grasp/contact logic; reserve gesture labels for
clear deliberate actions such as confirmation or stop signals.

## Training preparation

The mock procedure's six classes and an Ultralytics `data.yaml` are ready in
`data/tool_detection/`. Capture local source images with:

```bash
python scripts/capture_dataset.py --class-name sample_vial
```

Capture each class from varied angles, distances, lighting, and occlusion. Then
annotate every image with its bounding boxes in a local annotation tool, saving YOLO
`.txt` labels under the matching `labels/train` or `labels/val` directory. Use
`scripts/augment_check.py` to verify full-orientation augmentation and export a
trained local `best.pt` with `scripts/export_engine.py`.

### Collecting friends' photos

Share `scripts/contribute_images.py` with contributors. They place photos of one
class in a folder and run, for example:

```bash
python contribute_images.py --class-name sample_vial --input my-photos --contributor Alice --output alice-vials.zip
```

They send you the resulting ZIP. Import it without extracting untrusted files:

```bash
python scripts/import_contributions.py alice-vials.zip
```

The images arrive in `data/incoming_annotations/`; they must be annotated before
they can be used to train YOLO. Contributors should only send images they created
or have permission to share.
