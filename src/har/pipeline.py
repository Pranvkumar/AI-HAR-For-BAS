"""Threaded offline pipeline wiring ingestion, vision, fusion, FSM, and sinks."""

from dataclasses import dataclass
import argparse
import importlib
import queue
import threading
import time
from typing import Any

import yaml

from har.config.loader import load_protocol
from har.fsm.protocol_fsm import ProtocolFSM
from har.fusion.interaction_engine import InteractionEngine
from har.ingestion.camera import CameraSource, DropOldestQueue, FramePacket
from har.outputs.telemetry import TelemetryLogger
from har.outputs.tts import TTSWorker
from har.outputs.video import AnnotatedFrame, VideoRecorder, annotate_frame
from har.outputs.stream import create_app
from har.vision.mediapipe_wrapper import HandState, HandTracker
from har.vision.yolo_wrapper import Detection, YoloDetector


@dataclass(frozen=True)
class VisionPacket:
    frame: FramePacket
    detections: list[Detection]
    hands: HandState


class HARPipeline:
    def __init__(self, config_path: str = "configs/app.yaml") -> None:
        with open(config_path, encoding="utf-8") as stream:
            config = yaml.safe_load(stream) or {}
        self.config = config
        self.protocol = ProtocolFSM(load_protocol(config["protocol_path"]))
        with open(config.get("hardware_path", "configs/hardware.yaml"), encoding="utf-8") as stream:
            hardware = yaml.safe_load(stream) or {}
        self.raw = DropOldestQueue(maxsize=2)
        self.yolo_frames: queue.Queue[FramePacket] = queue.Queue(maxsize=2)
        self.hand_frames: queue.Queue[FramePacket] = queue.Queue(maxsize=2)
        self.yolo_results: queue.Queue[Any] = queue.Queue(maxsize=2)
        self.hand_results: queue.Queue[Any] = queue.Queue(maxsize=2)
        self.stream_frames: queue.Queue[AnnotatedFrame] = queue.Queue(maxsize=8)
        self.camera = CameraSource(config.get("video_source", 0), self.raw)
        self.detector = YoloDetector(config["model_path"], backend=hardware.get("yolo_backend", "auto"),
                                     frame_skip=hardware.get("frame_skip", 1) if hardware.get("frame_skip_enabled") else 1)
        self.hand_tracker = HandTracker()
        self.fusion = InteractionEngine()
        self.telemetry = TelemetryLogger(config.get("telemetry_path", "logs/events.jsonl"))
        self.tts = TTSWorker()
        self.video = VideoRecorder(config.get("video_path", "outputs/session.mp4"))
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []
        self.server: Any = None
        self.metrics: dict[str, dict[str, float]] = {}

    def _record(self, stage: str, elapsed: float) -> None:
        metric = self.metrics.setdefault(stage, {"count": 0.0, "seconds": 0.0})
        metric["count"] += 1
        metric["seconds"] += elapsed

    def start(self) -> None:
        self.telemetry.start()
        self.tts.start()
        self.video.start()
        self.camera.start()
        try:
            uvicorn = importlib.import_module("uvicorn")
            self.server = uvicorn.Server(uvicorn.Config(create_app(self.stream_frames), host=self.config.get("stream_host", "127.0.0.1"),
                                                        port=int(self.config.get("stream_port", 8000)), log_level="warning"))
            server_thread = threading.Thread(target=self.server.run, name="stream", daemon=True)
            server_thread.start()
            self.threads.append(server_thread)
        except ImportError:
            self.server = None
        for name, target in (("fanout", self._fanout), ("yolo", self._run_yolo), ("hands", self._run_hands), ("fusion", self._run_fusion)):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self.threads.append(thread)

    def _fanout(self) -> None:
        while not self.stop_event.is_set():
            try:
                packet = self.raw.get(timeout=0.1)
            except queue.Empty:
                continue
            self.yolo_frames.put(packet)
            self.hand_frames.put(packet)

    def _run_yolo(self) -> None:
        while not self.stop_event.is_set():
            try:
                packet = self.yolo_frames.get(timeout=0.1)
            except queue.Empty:
                continue
            started = time.perf_counter()
            detections = self.detector.detect(packet.frame)
            self._record("yolo", time.perf_counter() - started)
            self.yolo_results.put((packet, detections))

    def _run_hands(self) -> None:
        while not self.stop_event.is_set():
            try:
                packet = self.hand_frames.get(timeout=0.1)
            except queue.Empty:
                continue
            started = time.perf_counter()
            hands = self.hand_tracker.track(packet.frame, packet.timestamp)
            self._record("mediapipe", time.perf_counter() - started)
            self.hand_results.put((packet, hands))

    def _run_fusion(self) -> None:
        pending_yolo: dict[int, Any] = {}
        pending_hands: dict[int, Any] = {}
        while not self.stop_event.is_set():
            try:
                result = self.yolo_results.get(timeout=0.05)
                pending_yolo[result[0].frame_id] = result
            except queue.Empty:
                pass
            try:
                result = self.hand_results.get(timeout=0.05)
                pending_hands[result[0].frame_id] = result
            except queue.Empty:
                pass
            for frame_id in set(pending_yolo) & set(pending_hands):
                frame, detections = pending_yolo.pop(frame_id)
                _, hands = pending_hands.pop(frame_id)
                started = time.perf_counter()
                outputs = []
                for event in self.fusion.update(hands, detections):
                    outputs.extend(self.protocol.process(event))
                for result in outputs:
                    self.telemetry.submit(result)
                    self.tts.submit(result)
                self._record("fusion_fsm", time.perf_counter() - started)
                self._record("frames", 0.0)
                annotated = AnnotatedFrame(frame.timestamp, annotate_frame(frame.frame, detections, self.protocol.state))
                self.video.submit(annotated)
                try:
                    self.stream_frames.put_nowait(annotated)
                except queue.Full:
                    self.stream_frames.get_nowait()
                    self.stream_frames.put_nowait(annotated)

    def stop(self) -> None:
        self.stop_event.set()
        if self.server is not None:
            self.server.should_exit = True
        self.camera.stop()
        for thread in self.threads:
            thread.join(timeout=2)
        self.video.stop()
        self.tts.stop()
        self.telemetry.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/app.yaml")
    args = parser.parse_args()
    pipeline = HARPipeline(args.config)
    try:
        pipeline.start()
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
