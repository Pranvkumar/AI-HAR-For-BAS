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
    print(f"elapsed_seconds={time.monotonic() - started:.2f}")
    print("Run `nvidia-smi dmon` alongside this command to inspect GPU/NVENC load.")


if __name__ == "__main__":
    main()