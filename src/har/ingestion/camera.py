"""Threaded OpenCV frame capture with bounded drop-oldest buffering."""

from dataclasses import dataclass
import importlib
import queue
import threading
import time
from typing import Any


@dataclass(frozen=True)
class FramePacket:
    frame_id: int
    timestamp: float
    frame: Any


class DropOldestQueue(queue.Queue):
    """A bounded queue that preserves the newest frame when full."""

    def put_latest(self, item: Any) -> None:
        try:
            self.put_nowait(item)
        except queue.Full:
            self.get_nowait()
            self.put_nowait(item)


class CameraSource:
    def __init__(self, source: int | str = 0, output: DropOldestQueue | None = None) -> None:
        self.source = source
        self.output = output or DropOldestQueue(maxsize=2)
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="ingestion", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        cv2 = importlib.import_module("cv2")
        capture = cv2.VideoCapture(self.source)
        frame_id = 0
        try:
            while not self.stop_event.is_set():
                success, frame = capture.read()
                if not success:
                    break
                self.output.put_latest(FramePacket(frame_id, time.monotonic(), frame))
                frame_id += 1
        finally:
            capture.release()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
