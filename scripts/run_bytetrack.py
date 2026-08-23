"""Run local Ultralytics YOLO tracking with ByteTrack and save an annotated video."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    """Track local camera/video input using a local YOLO model file."""

    parser = argparse.ArgumentParser(description="Run local YOLO + ByteTrack tracking.")
    parser.add_argument("--model", type=Path, required=True, help="Local .pt, .onnx, or .engine model")
    parser.add_argument("--source", required=True, help="Camera number or local image/video path")
    parser.add_argument("--output", type=Path, default=Path("recordings/bytetrack"))
    parser.add_argument("--tracker", default="bytetrack.yaml", choices=("bytetrack.yaml", "botsort.yaml"))
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error(f"Model does not exist: {args.model}")
    import cv2
    from ultralytics import YOLO

    args.output.mkdir(parents=True, exist_ok=True)
    source: str | int = int(args.source) if args.source.isdigit() else args.source
    model = YOLO(str(args.model))
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        parser.error(f"Could not open local source: {args.source}")
    writer: cv2.VideoWriter | None = None
    frame_index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            result = model.track(frame, persist=True, tracker=args.tracker, verbose=False)[0]
            annotated = result.plot()
            if writer is None:
                height, width = annotated.shape[:2]
                writer = cv2.VideoWriter(str(args.output / "tracked.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 30, (width, height))
            writer.write(annotated)
            frame_index += 1
    finally:
        capture.release()
        if writer:
            writer.release()
    print(f"Tracked {frame_index} frames. Output: {args.output / 'tracked.mp4'}")


if __name__ == "__main__":
    main()
