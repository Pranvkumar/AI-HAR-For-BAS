"""Single-pass frame annotation and local OpenCV video recording."""

from dataclasses import dataclass
import importlib
from pathlib import Path
import queue
import threading
from typing import Any, Iterable


@dataclass(frozen=True)
class AnnotatedFrame:
    timestamp: float
    frame: Any


def annotate_frame(frame: Any, detections: Iterable[Any], state: str) -> Any:
    cv2 = importlib.import_module("cv2")
    output = frame.copy()
    for detection in detections:
        x1, y1, x2, y2 = (int(value) for value in detection.xyxy)
        cv2.rectangle(output, (x1, y1), (x2, y2), (40, 210, 160), 2)
        cv2.putText(output, f"{detection.cls} {detection.conf:.2f}", (x1, max(15, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 210, 160), 1)
    cv2.putText(output, f"Step: {state}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 220, 80), 2)
    return output


class VideoRecorder:
    def __init__(self, path: str | Path = "outputs/session.mp4", fps: float = 20.0) -> None:
        self.path = Path(path)
        self.fps = fps
        self.frames: queue.Queue[AnnotatedFrame] = queue.Queue(maxsize=8)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="video", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def submit(self, frame: AnnotatedFrame) -> None:
        try:
            self.frames.put_nowait(frame)
        except queue.Full:
            self.frames.get_nowait()
            self.frames.put_nowait(frame)

    def _run(self) -> None:
        cv2 = importlib.import_module("cv2")
        writer = None
        try:
            while not self.stop_event.is_set() or not self.frames.empty():
                try:
                    packet = self.frames.get(timeout=0.1)
                except queue.Empty:
                    continue
                if writer is None:
                    height, width = packet.frame.shape[:2]
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    writer = cv2.VideoWriter(str(self.path), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (width, height))
                    if not writer.isOpened():
                        raise RuntimeError(f"could not open video writer: {self.path}")
                writer.write(packet.frame)
        finally:
            if writer is not None:
                writer.release()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=3)
