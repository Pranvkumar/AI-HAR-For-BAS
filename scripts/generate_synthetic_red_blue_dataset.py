"""Generate a synthetic YOLO dataset for the red/blue microgravity procedure."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import yaml


CLASS_NAMES = [
    "main_container",
    "container_lid",
    "red_box",
    "blue_box",
    "astronaut_hand",
]


@dataclass(frozen=True)
class Label:
    cls: str
    box: tuple[int, int, int, int]


def _clamp_box(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    return (
        max(0, min(width - 1, x1)),
        max(0, min(height - 1, y1)),
        max(1, min(width, x2)),
        max(1, min(height, y2)),
    )


def _normalized(box: tuple[int, int, int, int], width: int, height: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    cx = ((x1 + x2) / 2.0) / width
    cy = ((y1 + y2) / 2.0) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return cx, cy, bw, bh


def _draw_box(image: np.ndarray, box: tuple[int, int, int, int], color: tuple[int, int, int], fill: bool = True) -> None:
    x1, y1, x2, y2 = box
    thickness = -1 if fill else 2
    cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)


def _hand_box(target: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    tx1, ty1, tx2, ty2 = target
    cx = (tx1 + tx2) // 2 + random.randint(-20, 20)
    cy = (ty1 + ty2) // 2 + random.randint(-20, 20)
    hw = random.randint(26, 40)
    hh = random.randint(26, 40)
    return _clamp_box((cx - hw, cy - hh, cx + hw, cy + hh), width, height)


def _make_scene(width: int, height: int, scenario: str) -> tuple[np.ndarray, list[Label]]:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :] = (
        random.randint(20, 40),
        random.randint(24, 44),
        random.randint(26, 46),
    )
    noise = np.random.randint(0, 12, (height, width, 3), dtype=np.uint8)
    image = cv2.add(image, noise)

    labels: list[Label] = []

    table_y = int(height * 0.72)
    cv2.rectangle(image, (0, table_y), (width, height), (58, 68, 80), -1)

    container_w = random.randint(320, 380)
    container_h = random.randint(170, 210)
    container_x1 = (width - container_w) // 2 + random.randint(-40, 40)
    container_y1 = int(height * 0.34) + random.randint(-18, 18)
    container = _clamp_box(
        (container_x1, container_y1, container_x1 + container_w, container_y1 + container_h),
        width,
        height,
    )
    _draw_box(image, container, (80, 110, 130), fill=True)
    cv2.rectangle(image, (container[0], container[1]), (container[2], container[3]), (24, 42, 55), 2)
    labels.append(Label("main_container", container))

    lid_h = random.randint(28, 38)
    lid_w = container[2] - container[0] + random.randint(-6, 8)
    lid_closed = _clamp_box((container[0], container[1] - lid_h, container[0] + lid_w, container[1]), width, height)
    lid_open_left = _clamp_box((container[0] - lid_w + 24, container[1] + 8, container[0] + 24, container[1] + lid_h + 8), width, height)

    open_lid = scenario in {
        "step2_red_out",
        "step3_blue_stacked",
        "spatial_error_blue_table",
        "sequence_error_blue_before_red",
    }
    lid = lid_open_left if open_lid else lid_closed
    _draw_box(image, lid, (132, 160, 182), fill=True)
    cv2.rectangle(image, (lid[0], lid[1]), (lid[2], lid[3]), (34, 52, 66), 2)
    labels.append(Label("container_lid", lid))

    red_boxes: list[tuple[int, int, int, int]] = []
    blue_boxes: list[tuple[int, int, int, int]] = []

    red_size = random.randint(56, 68)
    blue_size = random.randint(50, 62)

    inside_positions = [
        (container[0] + 40, container[1] + 60),
        (container[0] + 130, container[1] + 70),
        (container[0] + 220, container[1] + 66),
        (container[0] + 280, container[1] + 72),
    ]

    red_on_table = [
        (container[0] - 24, table_y - red_size - 10),
        (container[0] + 92, table_y - red_size - 12),
    ]

    if scenario in {"step1_open", "state_error_lid_closed_extract"}:
        red_boxes = [
            _clamp_box((inside_positions[0][0], inside_positions[0][1], inside_positions[0][0] + red_size, inside_positions[0][1] + red_size), width, height),
            _clamp_box((inside_positions[1][0], inside_positions[1][1], inside_positions[1][0] + red_size, inside_positions[1][1] + red_size), width, height),
        ]
    else:
        red_boxes = [
            _clamp_box((red_on_table[0][0], red_on_table[0][1], red_on_table[0][0] + red_size, red_on_table[0][1] + red_size), width, height),
            _clamp_box((red_on_table[1][0], red_on_table[1][1], red_on_table[1][0] + red_size, red_on_table[1][1] + red_size), width, height),
        ]

    if scenario in {"step1_open", "step2_red_out", "state_error_lid_closed_extract"}:
        blue_boxes = [
            _clamp_box((inside_positions[2][0], inside_positions[2][1], inside_positions[2][0] + blue_size, inside_positions[2][1] + blue_size), width, height),
            _clamp_box((inside_positions[3][0], inside_positions[3][1], inside_positions[3][0] + blue_size, inside_positions[3][1] + blue_size), width, height),
        ]
    elif scenario == "step3_blue_stacked":
        blue_boxes = [
            _clamp_box((red_boxes[0][0] + 6, red_boxes[0][1] - blue_size + 8, red_boxes[0][0] + 6 + blue_size, red_boxes[0][1] + 8), width, height),
            _clamp_box((red_boxes[1][0] + 6, red_boxes[1][1] - blue_size + 8, red_boxes[1][0] + 6 + blue_size, red_boxes[1][1] + 8), width, height),
        ]
    elif scenario == "spatial_error_blue_table":
        blue_boxes = [
            _clamp_box((container[0] + 230, table_y - blue_size - 8, container[0] + 230 + blue_size, table_y - 8), width, height),
            _clamp_box((container[0] + 308, table_y - blue_size - 10, container[0] + 308 + blue_size, table_y - 10), width, height),
        ]
    else:
        blue_boxes = [
            _clamp_box((container[0] + 220, table_y - blue_size - 10, container[0] + 220 + blue_size, table_y - 10), width, height),
            _clamp_box((container[0] + 298, table_y - blue_size - 10, container[0] + 298 + blue_size, table_y - 10), width, height),
        ]

    for red_box in red_boxes:
        _draw_box(image, red_box, (50, 50, 210), fill=True)
        cv2.rectangle(image, (red_box[0], red_box[1]), (red_box[2], red_box[3]), (28, 28, 96), 2)
        labels.append(Label("red_box", red_box))

    for blue_box in blue_boxes:
        _draw_box(image, blue_box, (210, 96, 40), fill=True)
        cv2.rectangle(image, (blue_box[0], blue_box[1]), (blue_box[2], blue_box[3]), (98, 48, 20), 2)
        labels.append(Label("blue_box", blue_box))

    focus_target = {
        "step1_open": lid,
        "step2_red_out": red_boxes[0],
        "step3_blue_stacked": blue_boxes[0],
        "spatial_error_blue_table": blue_boxes[0],
        "sequence_error_blue_before_red": blue_boxes[0],
        "state_error_lid_closed_extract": red_boxes[0],
    }.get(scenario, container)

    hand = _hand_box(focus_target, width, height)
    cv2.ellipse(
        image,
        ((hand[0] + hand[2]) // 2, (hand[1] + hand[3]) // 2),
        ((hand[2] - hand[0]) // 2, (hand[3] - hand[1]) // 2),
        random.randint(0, 160),
        0,
        360,
        (170, 190, 230),
        -1,
    )
    labels.append(Label("astronaut_hand", hand))

    if random.random() < 0.5:
        image = cv2.GaussianBlur(image, (3, 3), 0.6)

    return image, labels


def _write_sample(
    image_path: Path,
    label_path: Path,
    image: np.ndarray,
    labels: list[Label],
) -> None:
    image_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(image_path), image)
    height, width = image.shape[:2]
    with label_path.open("w", encoding="utf-8") as stream:
        for item in labels:
            cls_id = CLASS_NAMES.index(item.cls)
            cx, cy, bw, bh = _normalized(item.box, width, height)
            stream.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")


def generate_dataset(
    output_dir: Path,
    train_count: int,
    val_count: int,
    test_count: int,
    width: int,
    height: int,
    seed: int,
) -> None:
    random.seed(seed)
    np.random.seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [
        "step1_open",
        "step2_red_out",
        "step3_blue_stacked",
        "spatial_error_blue_table",
        "sequence_error_blue_before_red",
        "state_error_lid_closed_extract",
    ]

    splits = {
        "train": train_count,
        "val": val_count,
        "test": test_count,
    }

    metadata_path = output_dir / "metadata.jsonl"
    with metadata_path.open("w", encoding="utf-8") as metadata:
        for split, count in splits.items():
            for index in range(count):
                scenario = random.choice(scenarios)
                image, labels = _make_scene(width, height, scenario)
                stem = f"{split}_{index:05d}"
                image_path = output_dir / "images" / split / f"{stem}.jpg"
                label_path = output_dir / "labels" / split / f"{stem}.txt"
                _write_sample(image_path, label_path, image, labels)
                metadata.write(
                    json.dumps(
                        {
                            "split": split,
                            "id": stem,
                            "scenario": scenario,
                            "image": str(image_path.as_posix()),
                            "label": str(label_path.as_posix()),
                        }
                    )
                    + "\n"
                )

    data_yaml = {
        "path": str(output_dir.as_posix()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {index: name for index, name in enumerate(CLASS_NAMES)},
    }
    with (output_dir / "data.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(data_yaml, stream, sort_keys=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("datasets/red_blue_synth"))
    parser.add_argument("--train", type=int, default=480)
    parser.add_argument("--val", type=int, default=120)
    parser.add_argument("--test", type=int, default=80)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--seed", type=int, default=26174)
    args = parser.parse_args()

    generate_dataset(
        output_dir=args.output,
        train_count=args.train,
        val_count=args.val,
        test_count=args.test,
        width=args.width,
        height=args.height,
        seed=args.seed,
    )
    print(f"dataset_ready={args.output}")
    print(f"data_yaml={args.output / 'data.yaml'}")


if __name__ == "__main__":
    main()
