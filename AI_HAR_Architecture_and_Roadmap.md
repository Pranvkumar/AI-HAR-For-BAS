# AI HAR Architecture and Roadmap

Problem Statement 26174: an offline assistant for astronaut BAS experiments.

## Current Architecture

```text
Camera -> drop-oldest frame queue -> YOLO tracking + MediaPipe hands
       -> relational hand/object fusion -> config-driven protocol FSM
       -> JSONL telemetry, offline TTS, annotated MP4, MJPEG stream, dashboard
```

- `src/har/ingestion/` captures timestamped frames and bounds latency.
- `src/har/vision/` contains the YOLO adapter and CPU MediaPipe adapter.
- `src/har/fusion/` emits change-only events from hand/object relationships.
- `src/har/fsm/` validates ordered protocol evidence with debounce, lookback,
  and safety-critical blocking.
- `src/har/outputs/` contains asynchronous telemetry, TTS, video, and streaming
  sinks. The Streamlit dashboard is an optional local monitor.
- `configs/` owns protocol, hardware, and deployment choices. Runtime code must
  not assume gravity, fixed up/down directions, or a particular experiment.

## Active Demonstration

The maintained demonstration is the red/blue-box experiment:

```powershell
$env:PYTHONPATH = "src"
python scripts/build_red_blue_pipeline.py --epochs 25
python scripts/benchmark_pipeline.py --config configs/demo_red_blue_boxes_cpu.yaml --seconds 10
```

Synthetic data and labels live under `datasets/red_blue_synth/`. Generated
checkpoints, recordings, logs, and caches remain local and are ignored by Git.

## Deliberately Deferred

The following are optional follow-ups, not current runtime requirements:

- gesture labels for explicit confirmation or stop commands;
- a relational protocol-evidence engine for experiments beyond the box baseline;
- INT8 calibration and adaptive frame skipping after real-video benchmarks;
- a second camera, depth sensing, Kalman filtering, or temporal action models;
- a React dashboard or RTSP server in place of the current Streamlit/MJPEG path.

These should be added only when a real protocol or benchmark demonstrates the
need. The linked `har-microgravity-fluid-analysis` repository was used as a
comparison source; its planning prompts, biological-fluid mock, contribution
archive tools, and gesture demo are intentionally not copied into this focused
red/blue experiment repository.

## Verification

```powershell
python -m pip install -e ".[dev]"
pytest
```
