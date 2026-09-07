"""Self-contained offline demonstration of the HAR output and protocol path."""

from __future__ import annotations

import argparse
import logging
import threading
import time
from pathlib import Path

from har.config.loader import load_protocol
from har.events import Detection, InteractionEvent
from har.fsm.protocol_fsm import ProtocolFSM
from har.outputs.stream import AnnotatedFrameHub, create_app
from har.outputs.telemetry import TelemetryLogger
from har.outputs.tts import TTSWorker
from har.outputs.video import VideoRecorder


def run(protocol_path: str, output_dir: str, serve: bool = False) -> Path:
    """Create a deterministic local MP4 and JSONL run without camera or model assets."""

    import numpy as np

    protocol = load_protocol(protocol_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    telemetry = TelemetryLogger(destination)
    # Piper selection proves the asynchronous alert path without requiring audio hardware.
    tts = TTSWorker(backend="piper")
    telemetry.start()
    tts.start()

    def publish(event: object) -> None:
        telemetry.publish(event)
        tts.publish(event)

    fsm = ProtocolFSM(protocol, publish)
    hub = AnnotatedFrameHub()
    recorder = VideoRecorder(destination / "har-demo.mp4", fps=10, frame_size=(960, 540), frame_hub=hub)
    if serve:
        import uvicorn

        threading.Thread(
            target=lambda: uvicorn.run(create_app(hub), host="127.0.0.1", port=8000, log_level="warning"),
            daemon=True,
        ).start()
    try:
        timestamp = time.monotonic()
        for step in protocol.steps:
            object_class, interaction = step.expects[0].split(":", maxsplit=1)
            detection = Detection(object_class, 0.95, (320.0, 160.0, 640.0, 420.0), 1)
            for frame_index in range(protocol.debounce_frames):
                frame = np.zeros((540, 960, 3), dtype=np.uint8)
                frame[:, :] = (40, 25, 15)
                event = InteractionEvent(timestamp, "left", object_class, 1, interaction, interaction == "grasp", 0.5)
                fsm.handle(event)
                recorder.write(frame, [detection], fsm.current_step)
                timestamp += 0.1
    finally:
        recorder.close()
        tts.close()
        telemetry.close()
    return telemetry.path


def main() -> None:
    """Run the bundled synthetic demonstration."""

    parser = argparse.ArgumentParser(description="Run a fully local HAR demonstration.")
    parser.add_argument("--protocol", default="configs/demo_protocol.yaml")
    parser.add_argument("--output-dir", default="demo-output")
    parser.add_argument("--serve", action="store_true", help="Also serve the demo MJPEG stream on localhost:8000")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log_path = run(args.protocol, args.output_dir, args.serve)
    print(f"Demo complete. Telemetry: {log_path}")


if __name__ == "__main__":
    main()
