"""Offline queue-backed text-to-speech worker."""

import importlib
import logging
import queue
import threading
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)


class TTSWorker:
    def __init__(self, engine_factory: Callable[[], Any] | None = None) -> None:
        self.alert_queue: queue.Queue[Any] = queue.Queue()
        self.engine_factory = engine_factory or (lambda: importlib.import_module("pyttsx3").init())
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="tts", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def submit(self, event: Any) -> None:
        self.alert_queue.put(event)

    def _run(self) -> None:
        try:
            engine = self.engine_factory()
        except Exception:
            LOGGER.exception("TTS engine initialization failed")
            return
        while not self.stop_event.is_set() or not self.alert_queue.empty():
            try:
                event = self.alert_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                engine.say(getattr(event, "short_message", None) or getattr(event, "message", str(event)))
                engine.runAndWait()
            except Exception:
                LOGGER.exception("TTS playback failed")

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2)
