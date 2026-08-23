"""Non-blocking camera or video-file frame capture worker."""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FramePacket:
    """A captured frame with a monotonic timestamp."""

    frame_id: int
    timestamp_s: float
    frame: Any


def put_drop_oldest(target: queue.Queue[Any], item: Any) -> None:
    """Put an item without blocking, dropping the oldest item when full."""

    try:
        target.put_nowait(item)
    except queue.Full:
        try:
            target.get_nowait()
        except queue.Empty:
            return
        target.put_nowait(item)


class FrameCapture(threading.Thread):
    """Capture camera frames into a max-size-two drop-oldest queue."""

    def __init__(self, source: str | int, output: queue.Queue[FramePacket], stop_event: threading.Event) -> None:
        super().__init__(name="frame-capture", daemon=True)
        self.source, self.output, self.stop_event = source, output, stop_event

    def run(self) -> None:
        """Read frames until stopped or the source ends."""

        import cv2

        capture = cv2.VideoCapture(self.source)
        frame_id = 0
        try:
            while not self.stop_event.is_set():
                ok, frame = capture.read()
                if not ok:
                    break
                put_drop_oldest(self.output, FramePacket(frame_id, time.monotonic(), frame))
                frame_id += 1
        except Exception:
            LOGGER.exception("Capture failed at frame=%s stage=ingestion", frame_id)
        finally:
            capture.release()
            self.stop_event.set()
