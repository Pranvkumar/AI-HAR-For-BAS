"""Offline voice alerts.

The statement requires a *voice* alert on sequence violations, and requires the
whole system to run standalone. That rules out any cloud TTS. ``pyttsx3`` drives
the OS speech engine (SAPI5 on Windows, NSSpeech on macOS, espeak on Linux), so
audio stays entirely on the payload computer.

Two behaviours worth calling out:

* **Priority pre-emption.** A safety alert must not queue behind three routine
  "next step" prompts. Critical utterances jump the queue and flush pending
  routine ones.
* **Cooldown + dedup.** Without it, a violation that persists for 90 frames is
  spoken 90 times, which in a confined module is worse than no alert at all.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import queue
import threading
import time

LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover
    import pyttsx3
except Exception:  # pragma: no cover
    pyttsx3 = None  # type: ignore


PRIORITY_CRITICAL = 0
PRIORITY_WARNING = 1
PRIORITY_ROUTINE = 2


@dataclass(order=True)
class Utterance:
    priority: int
    sequence: int
    text: str = ""


class VoiceAnnouncer:
    """Threaded speech queue. Safe to call from the perception loop."""

    def __init__(self, *, rate: int = 165, volume: float = 1.0, cooldown_s: float = 2.5, enabled: bool = True) -> None:
        self.enabled = enabled and pyttsx3 is not None
        self.cooldown_s = cooldown_s
        self.rate = rate
        self.volume = volume
        self.available = pyttsx3 is not None
        self.error = "" if pyttsx3 is not None else "pyttsx3 not installed"
        self.spoken_count = 0
        self.last_text = ""

        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._seq = 0
        self._lock = threading.Lock()
        self._recent: dict[str, float] = {}
        self._transcript: list[tuple[float, str]] = []

    # ------------------------------------------------------------- lifecycle

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="voice", daemon=True)
        self._thread.start()

    def _make_engine(self):  # pragma: no cover - needs an audio device
        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", float(max(0.0, min(1.0, self.volume))))
        try:
            voices = engine.getProperty("voices")
            for v in voices:
                name = (getattr(v, "name", "") or "").lower()
                if any(tag in name for tag in ("zira", "female", "samantha", "hazel")):
                    engine.setProperty("voice", v.id)
                    break
        except Exception:
            pass
        return engine

    def _run(self) -> None:  # pragma: no cover - needs an audio device
        engine = None
        while not self._stop.is_set():
            try:
                item: Utterance = self._queue.get(timeout=0.3)
            except queue.Empty:
                continue
            if not self.enabled or pyttsx3 is None:
                continue
            try:
                # A fresh engine per utterance is slower but immune to the SAPI
                # deadlock that bites long-running single-engine loops on Windows.
                engine = self._make_engine()
                engine.say(item.text)
                engine.runAndWait()
                try:
                    engine.stop()
                except Exception:
                    pass
                with self._lock:
                    self.spoken_count += 1
                    self.last_text = item.text
                    self._transcript.append((time.time(), item.text))
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                LOGGER.warning("speech failed: %s", exc)
                time.sleep(0.5)
            finally:
                engine = None

    # ------------------------------------------------------------------ API

    def say(self, text: str, *, priority: int = PRIORITY_ROUTINE, force: bool = False) -> bool:
        """Queue an utterance. Returns False if it was suppressed."""
        text = (text or "").strip()
        if not text or not self.enabled:
            return False
        now = time.monotonic()
        with self._lock:
            last = self._recent.get(text, -1e9)
            cooldown = 0.0 if force else (self.cooldown_s if priority > PRIORITY_CRITICAL else 1.0)
            if now - last < cooldown:
                return False
            self._recent[text] = now
            self._seq += 1
            seq = self._seq

        if priority == PRIORITY_CRITICAL:
            self._drain_routine()
        self._queue.put(Utterance(priority, seq, text))
        return True

    def _drain_routine(self) -> None:
        keep: list[Utterance] = []
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item.priority <= PRIORITY_WARNING:
                keep.append(item)
        for item in keep:
            self._queue.put(item)

    def announce_event(self, event) -> bool:
        """Map a ProtocolEvent severity onto a speech priority."""
        speech = getattr(event, "speech", None)
        if not speech:
            return False
        severity = getattr(getattr(event, "severity", None), "value", "info")
        priority = {
            "critical": PRIORITY_CRITICAL,
            "warning": PRIORITY_WARNING,
        }.get(severity, PRIORITY_ROUTINE)
        return self.say(speech, priority=priority, force=(priority == PRIORITY_CRITICAL))

    def transcript(self) -> list[tuple[float, str]]:
        with self._lock:
            return list(self._transcript)

    def pending(self) -> int:
        return self._queue.qsize()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self._thread = None
