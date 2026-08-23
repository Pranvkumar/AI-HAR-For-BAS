"""Local benchmark harness for measuring complete pipeline runtime."""

import argparse
import time


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/app.yaml")
    parser.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args()
    from har.pipeline import HARPipeline
    pipeline = HARPipeline(args.config)
    started = time.monotonic()
    try:
        pipeline.start()
        time.sleep(args.seconds)
    finally:
        pipeline.stop()
    elapsed = time.monotonic() - started
    print(f"elapsed_seconds={elapsed:.2f}")
    frames = pipeline.metrics.get("frames", {}).get("count", 0)
    print(f"overall_fps={frames / elapsed:.2f}" if elapsed else "overall_fps=0.00")
    for stage, metric in sorted(pipeline.metrics.items()):
        if stage == "frames":
            continue
        average_ms = metric["seconds"] / metric["count"] * 1000 if metric["count"] else 0
        print(f"{stage}: count={int(metric['count'])} avg_ms={average_ms:.2f}")
    print("Run `nvidia-smi dmon` alongside this command to inspect GPU/NVENC load.")


if __name__ == "__main__":
    main()