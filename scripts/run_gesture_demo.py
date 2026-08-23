"""Show live offline MediaPipe hand-gesture recognition from a local camera."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from har.vision.gesture_recognizer import HandGestureRecognizer


def main() -> None:
    """Open a camera feed and render local recognized hand gestures."""

    parser = argparse.ArgumentParser(description="Run local MediaPipe gesture recognition.")
    parser.add_argument("--model", type=Path, default=Path("models/gesture_recognizer.task"))
    parser.add_argument("--source", default="0", help="Camera number or local video path")
    args = parser.parse_args()
    import cv2

    source: str | int = int(args.source) if args.source.isdigit() else args.source
    camera = cv2.VideoCapture(source)
    if not camera.isOpened():
        raise RuntimeError(f"Could not open local source: {args.source}")
    recognizer = HandGestureRecognizer(args.model)
    start = time.monotonic()
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                break
            results = recognizer.recognize(frame, int((time.monotonic() - start) * 1000))
            for index, item in enumerate(results):
                cv2.putText(frame, f"{item.handedness}: {item.name} ({item.confidence:.0%})", (20, 40 + index * 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, "MediaPipe Gesture Recognizer — press Q to stop", (20, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
            cv2.imshow("HAR hand gestures", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
    finally:
        recognizer.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
