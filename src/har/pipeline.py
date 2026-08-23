"""CLI orchestrator wiring local HAR stages and independent output consumers."""

from __future__ import annotations

import argparse
import logging
import queue
import threading
from pathlib import Path

from har.config.loader import load_app, load_protocol
from har.fsm.protocol_fsm import ProtocolFSM
from har.fusion.interaction_engine import InteractionEngine
from har.fusion.protocol_evidence import ProtocolEvidenceEngine
from har.ingestion.capture import FrameCapture, FramePacket
from har.outputs.stream import AnnotatedFrameHub, create_app
from har.outputs.telemetry import TelemetryLogger
from har.outputs.tts import TTSWorker
from har.outputs.video import VideoRecorder
from har.vision.mediapipe_wrapper import HandTracker
from har.vision.yolo_wrapper import YoloDetector

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the documented pipeline command-line interface."""

    parser = argparse.ArgumentParser(description="Run the offline HAR pipeline.")
    parser.add_argument("--config", default="configs/app.yaml")
    parser.add_argument("--source", help="Camera number or local video path; overrides config.")
    return parser


def run(config_path: str, source_override: str | None = None) -> None:
    """Start local capture, vision, FSM, recording, and MJPEG serving."""

    import uvicorn

    app_config = load_app(config_path)
    protocol = load_protocol(Path(config_path).parent / Path(app_config.protocol_path).name)
    pipeline = app_config.pipeline
    source = source_override if source_override is not None else pipeline.get("source", 0)
    raw_frames: queue.Queue[FramePacket] = queue.Queue(maxsize=2)
    stop_event = threading.Event()
    telemetry, tts = TelemetryLogger(app_config.outputs.get("logs_dir", "logs")), TTSWorker(app_config.tts.get("backend", "pyttsx3"))
    telemetry.start()
    tts.start()

    def publish(event: object) -> None:
        telemetry.publish(event)
        tts.publish(event)

    fsm = ProtocolFSM(protocol, publish)
    interactions = InteractionEngine()
    protocol_evidence = ProtocolEvidenceEngine()
    detector = YoloDetector(pipeline["model_path"], backend=pipeline.get("backend", "tensorrt"), frame_skip=int(pipeline.get("adaptive_frame_skip", 1)))
    hands = HandTracker()
    hub = AnnotatedFrameHub()
    recorder: VideoRecorder | None = None
    capture = FrameCapture(int(source) if str(source).isdigit() else source, raw_frames, stop_event)
    capture.start()
    server = threading.Thread(target=lambda: uvicorn.run(create_app(hub), host="127.0.0.1", port=int(app_config.outputs.get("stream_port", 8000)), log_level="warning"), daemon=True)
    server.start()
    try:
        while not stop_event.is_set() or not raw_frames.empty():
            try:
                packet = raw_frames.get(timeout=0.2)
            except queue.Empty:
                continue
            detections = detector.detect(packet.frame)
            hand_state = hands.track(packet.frame)
            height, width = packet.frame.shape[:2]
            hand_events = interactions.process(hand_state, detections, (width, height))
            for interaction in hand_events + protocol_evidence.process(detections, hand_events, packet.timestamp_s):
                fsm.handle(interaction)
            if recorder is None:
                recorder = VideoRecorder(app_config.outputs.get("video_path", "recordings/har.mp4"), float(pipeline.get("fps", 30)), (width, height), hub)
            recorder.write(packet.frame, detections, fsm.current_step)
    except KeyboardInterrupt:
        LOGGER.info("Pipeline stopped by user")
    finally:
        stop_event.set()
        capture.join(2.0)
        if recorder:
            recorder.close()
        hands.close()
        tts.close()
        telemetry.close()


def main() -> None:
    """Run the command-line entry point."""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args()
    run(args.config, args.source)


if __name__ == "__main__":
    main()
