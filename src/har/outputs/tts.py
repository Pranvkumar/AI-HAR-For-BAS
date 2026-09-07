"""Non-blocking offline text-to-speech worker."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any

LOGGER = logging.getLogger(__name__)


class TTSWorker:
    """Speak short event messages on a dedicated CPU-only worker thread."""

    def __init__(self, backend: str = "pyttsx3") -> None:
        if backend not in {"pyttsx3", "piper"}:
            raise ValueError("backend must be 'pyttsx3' or 'piper'")
        self.backend = backend
        self.alert_queue: queue.Queue[Any | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="tts-worker", daemon=True)

    def start(self) -> None:
        """Start the TTS worker."""

        self._thread.start()

    def publish(self, event: Any) -> None:
        """Queue an alert without blocking protocol processing."""

        self.alert_queue.put_nowait(event)

    def _speak(self, message: str) -> None:
        if self.backend == "piper":
            LOGGER.warning("Piper backend is configured but not yet provisioned; alert logged: %s", message)
            return
        import pyttsx3

        engine = pyttsx3.init()
        engine.say(message)
        engine.runAndWait()

    def _run(self) -> None:
        while True:
            event = self.alert_queue.get()
            if event is None:
                return
            message = getattr(event, "short_message", None)
            if not message:
                continue
            try:
                self._speak(str(message))
            except Exception:
                LOGGER.exception("TTS failed stage=tts")

    def close(self, timeout_s: float = 2.0) -> None:
        """Stop after the current alert."""

        self.alert_queue.put(None)
        self._thread.join(timeout_s)
