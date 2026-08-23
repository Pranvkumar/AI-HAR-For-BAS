"""Queue-backed append-only JSON Lines telemetry writer."""

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
import queue
import threading
import time
from typing import Any


class TelemetryLogger:
    def __init__(self, path: str | Path = "logs/events.jsonl") -> None:
        self.path = Path(path)
        self.events: queue.Queue[Any] = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="telemetry", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def submit(self, event: Any) -> None:
        self.events.put(event)

    def _run(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            while not self.stop_event.is_set() or not self.events.empty():
                try:
                    event = self.events.get(timeout=0.1)
                except queue.Empty:
                    continue
                payload = asdict(event) if is_dataclass(event) else event
                stream.write(json.dumps({"timestamp_written": time.time(), "event": payload}, default=str) + "\n")
                stream.flush()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2)
