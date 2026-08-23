"""Benchmark local pipeline stages against a fixed local video."""

from __future__ import annotations

import argparse
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure local video read throughput before full-sink profiling.")
    parser.add_argument("video")
    parser.add_argument("--seconds", type=float, default=30.0)
    args = parser.parse_args()
    import cv2

    capture, started, frames = cv2.VideoCapture(args.video), time.perf_counter(), 0
    while time.perf_counter() - started < args.seconds:
        ok, _ = capture.read()
        if not ok:
            break
        frames += 1
    elapsed = time.perf_counter() - started
    capture.release()
    print(f"ingestion_fps={frames / elapsed:.2f}; frames={frames}; elapsed_s={elapsed:.2f}")
    print("Run 'nvidia-smi dmon' alongside the complete pipeline to capture GPU/encoder utilization.")


if __name__ == "__main__":
    main()
