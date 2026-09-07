"""Download the official MediaPipe Gesture Recognizer model during setup only."""

from __future__ import annotations

import argparse
import shutil
import urllib.request
from pathlib import Path

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task"


def main() -> None:
    """Download the public model bundle once for later fully local inference."""

    parser = argparse.ArgumentParser(description="Download the official MediaPipe gesture model for offline use.")
    parser.add_argument("--output", type=Path, default=Path("models/gesture_recognizer.task"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        print(f"Model already exists: {args.output}")
        return
    print("Downloading official MediaPipe gesture model for one-time local setup...")
    with urllib.request.urlopen(MODEL_URL) as response, args.output.open("wb") as destination:
        shutil.copyfileobj(response, destination)
    print(f"Saved {args.output}. Future gesture recognition is local.")


if __name__ == "__main__":
    main()
