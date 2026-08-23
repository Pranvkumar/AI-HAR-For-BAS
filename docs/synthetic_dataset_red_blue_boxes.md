# Synthetic Dataset Plan: Red-Blue Box Experiment

This guide defines a focused local dataset for the 4-step experiment:

1. Open the main box.
2. Place two red boxes side-by-side.
3. Place two blue boxes stacked on top of the red boxes.
4. Close the main box.

## 1) Labels and Scene Objects

Use a small, task-specific detection label set:

- main_container
- container_lid
- red_box
- blue_box
- astronaut_hand

Optional relational helper labels for easier rule logic:

- red_box_pair
- blue_box_stack

Notes:

- Keep colors and textures of red/blue boxes visually distinct.
- Keep the main container and lid visible in every clip.

## 2) Capture Targets (Webcam Dataset)

Record short clips (10-20 seconds each) with step-level diversity:

- Camera angle: top-left, top-right, frontal, shallow angle.
- Lighting: bright, medium, dim.
- Background: clean table, cluttered table, reflective table.
- Hand usage: left hand, right hand, both hands.
- Motion speed: slow, normal, fast.

Minimum useful dataset size for a first local model:

- 80 to 120 clips total.
- At least 20 clips per step where that step is clearly dominant.
- At least 20 negative clips containing off-protocol actions.

## 3) Annotation Rules

Detection annotations:

- Draw tight boxes around each visible red_box and blue_box.
- Draw box around main_container and container_lid when visible.
- Do not merge two same-color boxes into one box.

Temporal step annotations (sidecar CSV or JSONL):

- clip_id
- t_start_s
- t_end_s
- step_id (1..4)
- quality_flag (clean or noisy)

This lets you evaluate sequence compliance independently from detector quality.

## 4) Relational Event Derivation

The current interaction engine emits object-state changes based on hand overlap and pinch/contact.
Map detection outputs to protocol objects before FSM input:

- red_box_pair: true when two red_box detections are present and horizontally adjacent.
- blue_box_stack: true when two blue_box detections are vertically stacked and overlap one red_box each.
- container_lid contact/open-close: inferred by astronaut_hand overlap with container_lid and lid pose/position changes relative to main_container.

## 5) Recommended Train/Validation Split

- Train: 70%
- Validation: 20%
- Test: 10%

Split by recording session, not by individual frames, to avoid leakage.

## 6) Local Evaluation Checklist

- Step order accuracy across full clip.
- Missed-step false negatives.
- Safety-critical handling at step 3 (stacking blue on red).
- End-to-end runtime on CPU at webcam resolution.

## 7) Run Command for This Scenario

Use the scenario config after installing dependencies:

PYTHONPATH=src python scripts/benchmark_pipeline.py --config configs/demo_red_blue_boxes_cpu.yaml --seconds 10

On PowerShell:

$env:PYTHONPATH = "src"
python scripts/benchmark_pipeline.py --config configs/demo_red_blue_boxes_cpu.yaml --seconds 10