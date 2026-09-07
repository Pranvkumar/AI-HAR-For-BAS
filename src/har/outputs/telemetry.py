"""Thread-safe append-only JSON Lines telemetry output."""

from __future__ import annotations

import json
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from har.events import event_to_dict


class TelemetryLogger:
    """Write typed FSM events on one dedicated thread."""

    def __init__(self, directory: str | Path = "logs") -> None:
        directory_path = Path(directory)
        directory_path.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = directory_path / f"har-{stamp}.jsonl"
        self.queue: queue.Queue[Any | None] = queue.Queue()
        self._thread = threading.Thread(target=self._write, name="telemetry-writer", daemon=True)

    def start(self) -> None:
        """Start the writer thread."""

        self._thread.start()

    def publish(self, event: Any) -> None:
        """Queue an event without blocking a vision worker."""

        self.queue.put_nowait(event)

    def _write(self) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            while True:
                event = self.queue.get()
                if event is None:
                    return
                handle.write(json.dumps(event_to_dict(event), default=str) + "\n")
                handle.flush()

    def close(self, timeout_s: float = 2.0) -> None:
        """Flush queued data and stop the writer."""

        self.queue.put(None)
        self._thread.join(timeout_s)
