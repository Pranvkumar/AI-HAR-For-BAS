"""Capture locally labelled-by-folder source images for HAR model annotation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

OBJECT_CLASSES = (
    "sample_vial",
    "reagent_pipette",
    "rack_holder",
    "centrifuge_slot",
    "centrifuge_lid",
    "astronaut_hand",
)


def main() -> None:
    """Capture frames from a local camera; annotations are intentionally manual."""

    parser = argparse.ArgumentParser(description="Capture local HAR training images.")
    parser.add_argument("--class-name", choices=OBJECT_CLASSES, required=True)
    parser.add_argument("--source", default="0", help="Camera number or local video path")
    parser.add_argument("--split", choices=("train", "val"), default="train")
    parser.add_argument("--output", type=Path, default=Path("data/tool_detection/images"))
    args = parser.parse_args()
    import cv2

    source = int(args.source) if args.source.isdigit() else args.source
    target = args.output / args.split
    target.mkdir(parents=True, exist_ok=True)
    camera = cv2.VideoCapture(source)
    if not camera.isOpened():
        raise RuntimeError(f"Could not open local capture source: {args.source}")
    print("Press SPACE to capture, Q to finish. Vary orientation, distance, lighting, and occlusion.")
    sequence = 0
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                break
            cv2.putText(frame, f"{args.class_name} | SPACE: capture | Q: quit", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow("HAR dataset capture", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                path = target / f"{args.class_name}_{stamp}_{sequence:04d}.jpg"
                cv2.imwrite(str(path), frame)
                print(f"Saved {path}")
                sequence += 1
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
