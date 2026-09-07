"""Tests for asynchronous telemetry and text-to-speech output contracts."""

from __future__ import annotations

import json
import time

from har.events import ViolationEvent
from har.outputs.telemetry import TelemetryLogger
from har.outputs.tts import TTSWorker


def test_telemetry_writes_json_line(tmp_path) -> None:
    logger = TelemetryLogger(tmp_path)
    logger.start()
    logger.publish(ViolationEvent(1.0, "full", "short", False))
    logger.close()
    payload = json.loads(logger.path.read_text(encoding="utf-8"))
    assert payload["event_type"] == "ViolationEvent"


def test_tts_worker_uses_short_message(monkeypatch) -> None:
    spoken: list[str] = []
    worker = TTSWorker()
    monkeypatch.setattr(worker, "_speak", spoken.append)
    worker.start()
    worker.publish(ViolationEvent(1.0, "full", "short", False))
    for _ in range(20):
        if spoken:
            break
        time.sleep(0.01)
    worker.close()
    assert spoken == ["short"]
