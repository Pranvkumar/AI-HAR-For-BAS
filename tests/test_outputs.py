from dataclasses import dataclass
import json
import time

from har.ingestion.camera import DropOldestQueue
from har.outputs.telemetry import TelemetryLogger
from har.outputs.tts import TTSWorker


@dataclass(frozen=True)
class Event:
    message: str


def test_drop_oldest_queue_keeps_latest_item():
    items = DropOldestQueue(maxsize=2)
    items.put_latest(1)
    items.put_latest(2)
    items.put_latest(3)
    assert [items.get(), items.get()] == [2, 3]


def test_telemetry_worker_writes_jsonl(tmp_path):
    path = tmp_path / "events.jsonl"
    logger = TelemetryLogger(path)
    logger.start()
    logger.submit(Event("completed"))
    logger.stop()
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["event"]["message"] == "completed"


def test_tts_worker_uses_injected_engine():
    spoken = []

    class Engine:
        def say(self, message):
            spoken.append(message)

        def runAndWait(self):
            pass

    worker = TTSWorker(lambda: Engine())
    worker.start()
    worker.submit(Event("short alert"))
    for _ in range(20):
        if spoken:
            break
        time.sleep(0.01)
    worker.stop()
    assert spoken == ["short alert"]
