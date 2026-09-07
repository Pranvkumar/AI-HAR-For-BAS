# AI HAR for Astronaut BAS Experiments

This repository implements a local Human Activity Recognition prototype for SIH
2026 Problem Statement 26174: **AI Human Activity Recognition for On-board BAS
Experiments**. It supports astronauts carrying out predefined procedures in
microgravity by validating a sequence of visible actions without continuous
ground communication.

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

This repository includes the offline inference models in `models/`. The default configuration uses the bundled YOLO weights and MediaPipe gesture model, so no model download is required. Then run:

```bash
python scripts/run_pipeline.py --config configs/app.yaml --source path/to/local-video.mp4
```

For Windows setup and camera instructions, see [`RUN_INSTRUCTIONS.md`](RUN_INSTRUCTIONS.md).

It records an annotated MP4, writes JSON Lines telemetry, and serves an MJPEG stream at `http://127.0.0.1:8000/stream`. In a second terminal, start the local dashboard:

```bash
streamlit run src/har/outputs/gui/dashboard.py
```

## Immediate offline demo

Run the complete local output and protocol path without a camera, model weights, or
network access:

```bash
python scripts/run_sih_demo.py
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
validates tracking only; it cannot recognize the project-specific outer container
or inner boxes until the custom model is trained.

## Hand gesture recognition

For robust, detailed hand input, this project also supports MediaPipe Gesture
Recognizer alongside YOLO/ByteTrack. The official model is bundled at
`models/gesture_recognizer.task`. It recognizes `Closed_Fist`, `Open_Palm`,
`Pointing_Up`, `Thumb_Down`, `Thumb_Up`, `Victory`, and `ILoveYou`, and provides
21 landmarks per hand. Download its official model once during setup:

```bash
python -m pip install mediapipe
python scripts/download_gesture_model.py
python scripts/run_gesture_demo.py --source 0
```

The model is included for offline handoff and inference runs locally afterwards.
Use the landmark information for grasp/contact logic; reserve gesture labels for
clear deliberate actions such as confirmation or stop signals.

## SIH visible-box baseline

The available SIH statement specifies a synthetic sample experiment with an
outer box containing a red inner box and a second coloured inner box. The
official text visible to us does not show the second colour or full sequence, so
the active baseline uses `second_colored_box` rather than guessing it.

It validates this conservative procedure entirely through relative observations:

1. Retrieve the red box from the outer container.
2. Retrieve the second coloured box.
3. Return the red box.
4. Return the second coloured box.

The classes, sequence, debounce settings, and safety handling are all in
`configs/protocol.yaml`; edit the YAML once ISRO/SIH publishes the remaining
details. The separate biological-fluid mock is retained only as a technical
reference in `configs/mock_biological_fluid_protocol.yaml`.

## Training preparation

The active SIH box dataset is ready in `data/sih_box_experiment/`, with
`outer_container`, `red_box`, `second_colored_box`, and `astronaut_hand`
classes. Capture local source images with:

```bash
python scripts/capture_dataset.py --class-name red_box
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
python contribute_images.py --class-name red_box --input my-photos --contributor Alice --output alice-red-boxes.zip
```

They send you the resulting ZIP. Import it without extracting untrusted files:

```bash
python scripts/import_contributions.py alice-vials.zip
```

The images arrive in `data/incoming_annotations/`; they must be annotated before
they can be used to train YOLO. Contributors should only send images they created
or have permission to share.
