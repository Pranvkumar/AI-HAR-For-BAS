"""Watchdog supervisor.

A long-running console with seven background threads will eventually lose one.
The failure mode that matters is not the crash -- it is the *silence* afterwards:
the recorder thread dies, the GUI keeps showing a green lamp, and forty minutes
of experiment go unrecorded.

This supervisor requires every worker to prove it is alive. A worker that stops
beating is declared faulted, restarted if it declared a restart callback, and
surfaced to the operator either way. Nothing fails quietly.

Design notes
------------
* **Heartbeats are pull, not push.** Workers call :meth:`beat` from inside their
  own loop. A thread that is alive but wedged on a blocking call therefore still
  registers as faulted, which a simple ``thread.is_alive()`` check would miss --
  and a wedged thread is the more common failure.
* **Restarts are budgeted.** A worker that fails repeatedly is left down and
  reported rather than restarted forever, because a restart loop hides the
  underlying fault and burns CPU during a demo.
* **The supervisor never raises into the pipeline.** It reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
import threading
import time
from typing import Callable

LOGGER = logging.getLogger(__name__)


class WorkerState(str, Enum):
    STARTING = "starting"
    HEALTHY = "healthy"
    STALLED = "stalled"      # missed its deadline, not yet declared dead
    FAULTED = "faulted"      # declared dead
    RESTARTING = "restarting"
    STOPPED = "stopped"      # deliberately stopped, not a fault
    DISABLED = "disabled"    # exhausted its restart budget


@dataclass
class Worker:
    name: str
    timeout_s: float = 5.0
    critical: bool = False
    restart: Callable[[], bool] | None = None
    max_restarts: int = 3

    state: WorkerState = WorkerState.STARTING
    last_beat: float = field(default_factory=time.monotonic)
    beats: int = 0
    restarts: int = 0
    faults: int = 0
    last_fault: str = ""
    registered: float = field(default_factory=time.monotonic)

    @property
    def silence_s(self) -> float:
        return time.monotonic() - self.last_beat

    @property
    def healthy(self) -> bool:
        return self.state in (WorkerState.HEALTHY, WorkerState.STARTING)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "critical": self.critical,
            "silence_s": round(self.silence_s, 2),
            "beats": self.beats,
            "restarts": self.restarts,
            "faults": self.faults,
            "last_fault": self.last_fault,
        }


class Supervisor:
    """Monitors worker heartbeats and restarts what it can."""

    def __init__(self, *, poll_s: float = 1.0, grace_s: float = 3.0) -> None:
        self.poll_s = poll_s
        self.grace_s = grace_s          # startup grace before enforcing deadlines
        self.workers: dict[str, Worker] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._listeners: list[Callable[[Worker, WorkerState], None]] = []

    # ------------------------------------------------------------ registration

    def register(
        self,
        name: str,
        *,
        timeout_s: float = 5.0,
        critical: bool = False,
        restart: Callable[[], bool] | None = None,
        max_restarts: int = 3,
    ) -> Worker:
        with self._lock:
            worker = Worker(name, timeout_s, critical, restart, max_restarts)
            self.workers[name] = worker
            return worker

    def unregister(self, name: str) -> None:
        with self._lock:
            self.workers.pop(name, None)

    def on_state_change(self, callback: Callable[[Worker, WorkerState], None]) -> None:
        self._listeners.append(callback)

    def _emit(self, worker: Worker, previous: WorkerState) -> None:
        for cb in list(self._listeners):
            try:
                cb(worker, previous)
            except Exception as exc:  # pragma: no cover
                LOGGER.debug("supervisor listener failed: %s", exc)

    # --------------------------------------------------------------- heartbeat

    def beat(self, name: str) -> None:
        """Called by a worker from inside its own loop, every iteration."""
        with self._lock:
            worker = self.workers.get(name)
            if worker is None:
                return
            worker.last_beat = time.monotonic()
            worker.beats += 1
            if worker.state in (WorkerState.STARTING, WorkerState.STALLED,
                                WorkerState.RESTARTING, WorkerState.FAULTED):
                previous = worker.state
                worker.state = WorkerState.HEALTHY
                if previous is not WorkerState.STARTING:
                    LOGGER.info("worker %s recovered from %s", name, previous.value)
                self._emit(worker, previous)

    def report_fault(self, name: str, reason: str) -> None:
        """A worker can declare its own failure rather than waiting for silence."""
        with self._lock:
            worker = self.workers.get(name)
            if worker is None:
                return
            previous = worker.state
            worker.state = WorkerState.FAULTED
            worker.faults += 1
            worker.last_fault = reason
        self._emit(worker, previous)

    def stopped(self, name: str) -> None:
        """Mark a deliberate stop so it is not reported as a fault."""
        with self._lock:
            worker = self.workers.get(name)
            if worker is None:
                return
            previous, worker.state = worker.state, WorkerState.STOPPED
        self._emit(worker, previous)

    # ---------------------------------------------------------------- checking

    def check(self) -> list[Worker]:
        """One supervision pass. Returns workers whose state changed."""
        changed: list[Worker] = []
        now = time.monotonic()

        with self._lock:
            candidates = list(self.workers.values())

        for worker in candidates:
            if worker.state in (WorkerState.STOPPED, WorkerState.DISABLED):
                continue
            if now - worker.registered < self.grace_s and worker.beats == 0:
                continue

            silence = worker.silence_s
            previous = worker.state

            if silence > worker.timeout_s * 2:
                if worker.state is not WorkerState.FAULTED:
                    worker.state = WorkerState.FAULTED
                    worker.faults += 1
                    worker.last_fault = f"no heartbeat for {silence:.1f}s"
                    LOGGER.warning("worker %s faulted: %s", worker.name, worker.last_fault)
                    changed.append(worker)
                    self._emit(worker, previous)
                self._try_restart(worker)

            elif silence > worker.timeout_s:
                if worker.state is not WorkerState.STALLED:
                    worker.state = WorkerState.STALLED
                    changed.append(worker)
                    self._emit(worker, previous)

        return changed

    def _try_restart(self, worker: Worker) -> None:
        if worker.restart is None:
            return
        if worker.restarts >= worker.max_restarts:
            if worker.state is not WorkerState.DISABLED:
                previous, worker.state = worker.state, WorkerState.DISABLED
                LOGGER.error("worker %s exhausted its restart budget (%d)",
                             worker.name, worker.max_restarts)
                self._emit(worker, previous)
            return

        previous = worker.state
        worker.state = WorkerState.RESTARTING
        worker.restarts += 1
        self._emit(worker, previous)
        LOGGER.info("restarting worker %s (attempt %d/%d)",
                    worker.name, worker.restarts, worker.max_restarts)
        try:
            ok = bool(worker.restart())
        except Exception as exc:
            ok = False
            worker.last_fault = f"restart raised {type(exc).__name__}: {exc}"
            LOGGER.error("restart of %s failed: %s", worker.name, exc)
        if ok:
            worker.last_beat = time.monotonic()
        else:
            worker.state = WorkerState.FAULTED

    # -------------------------------------------------------------- lifecycle

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="supervisor", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.check()
            except Exception as exc:  # pragma: no cover
                LOGGER.error("supervision pass failed: %s", exc)
            self._stop.wait(self.poll_s)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None

    # ---------------------------------------------------------------- readout

    @property
    def all_healthy(self) -> bool:
        with self._lock:
            return all(w.healthy or w.state is WorkerState.STOPPED for w in self.workers.values())

    @property
    def critical_fault(self) -> bool:
        """True when a worker marked critical is down. The pipeline should
        suspend validation rather than continue with a hole in it."""
        with self._lock:
            return any(
                w.critical and w.state in (WorkerState.FAULTED, WorkerState.DISABLED)
                for w in self.workers.values()
            )

    def faulted(self) -> list[Worker]:
        with self._lock:
            return [w for w in self.workers.values()
                    if w.state in (WorkerState.FAULTED, WorkerState.DISABLED)]

    def snapshot(self) -> dict:
        with self._lock:
            workers = [w.to_dict() for w in self.workers.values()]
        return {
            "all_healthy": self.all_healthy,
            "critical_fault": self.critical_fault,
            "workers": workers,
        }

    def summary(self) -> str:
        faulted = self.faulted()
        if not faulted:
            return f"{len(self.workers)} workers nominal"
        return "FAULT: " + ", ".join(f"{w.name} ({w.last_fault})" for w in faulted)
