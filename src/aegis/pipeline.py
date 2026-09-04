"""Session orchestrator: capture -> perception -> validation -> outputs.

Threading model
---------------
* capture thread   (in :mod:`aegis.capture.source`) grabs frames, keeps latest
* pipeline thread  (here) does perception + validation + annotation
* recorder thread  writes video
* MJPEG threads    serve clients
* voice thread     speaks

The GUI never blocks on any of these: it polls :meth:`snapshot` and
:meth:`latest_frame`. That means a hung speech engine or a wedged network client
cannot freeze the operator's display, which is exactly the failure mode you do
not want on a payload console.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import logging
from pathlib import Path
import threading
import time
from typing import Callable

import numpy as np

from aegis.capture.recorder import VideoRecorder, new_session_id
from aegis.capture.source import VideoSource
from aegis.capture.streamer import VideoStreamer
from aegis.config import AppConfig
from aegis.outputs.logbook import Logbook
from aegis.outputs.overlay import OverlayState, draw, placeholder
from aegis.outputs.voice import VoiceAnnouncer
from aegis.perception.landmarks import LandmarkExtractor, attach_rack_coords
from aegis.perception.rack_frame import RackTracker, identity_frame
from aegis.perception.recognizer import LearnedRecognizer, RecognitionEngine
from aegis.perception.zones import ZoneSet
from aegis.protocol.engine import Observation, ProtocolEngine, ProtocolEvent, Severity
from aegis.protocol.spec import Protocol, load_protocol
from aegis.fusion.evidence import Evidence, EvidenceFuser, Source, Verdict, camera_veto
from aegis.fusion.interaction import InteractionEngine
from aegis.outputs.audit import AuditTrail, EventLevel
from aegis.perception.quality import FrameQualityMonitor, HealthState
from aegis.perception.rack_health import RackHealthManager
from aegis.perception.tracking import ObjectStateMachine, ObjectTracker
from aegis.perception.objects import build_detector
from aegis.fusion.object_evidence import ObjectVerifier
from aegis.fusion.protocol_evidence import NestedContainerEvidence
from aegis.safety.failure_injection import FailureInjector, FaultType
from aegis.safety.modes import Mode, ModeManager
from aegis.safety.watchdog import Supervisor

LOGGER = logging.getLogger(__name__)


@dataclass
class PipelineStatus:
    running: bool = False
    session_id: str = ""
    camera_ok: bool = False
    camera_desc: str = ""
    camera_error: str = ""
    perception: str = ""
    tier: str = ""
    tier_detail: str = ""
    rack_source: str = "-"
    rack_confidence: float = 0.0
    fps: float = 0.0
    latency_ms: float = 0.0
    frames: int = 0
    zones_calibrated: bool = False
    recording: bool = False
    record_path: str = ""
    streaming: bool = False
    stream_url: str = ""
    stream_clients: int = 0
    voice_ok: bool = False
    voice_error: str = ""
    log_path: str = ""
    last_action: str = ""
    last_confidence: float = 0.0
    errors: list[str] = field(default_factory=list)
    # --- Round 2 -----------------------------------------------------
    mode: str = "standby"
    camera_health: str = "nominal"
    camera_reasons: list[str] = field(default_factory=list)
    rack_health: str = "red"
    rack_summary: str = ""
    verdict: str = ""
    verdict_reason: str = ""
    explanation: str = ""
    tracked_objects: int = 0
    interaction_events: int = 0
    workers_ok: bool = True
    worker_summary: str = ""
    injected_faults: list[str] = field(default_factory=list)
    audit_head: str = ""
    detector_ok: bool = False
    detector_desc: str = ""
    detector_latency_ms: float = 0.0
    object_match: str = ""
    object_summary: str = ""
    detected_labels: list[str] = field(default_factory=list)
    audit_entries: int = 0


class HARPipeline:
    """One experiment session, end to end."""

    def __init__(self, config: AppConfig, *, on_event: Callable[[ProtocolEvent], None] | None = None) -> None:
        self.config = config
        self.on_event = on_event
        self.protocol: Protocol = load_protocol(config.protocol_file)

        self.zones = ZoneSet.load(config.zones_file)
        self._zones_calibrated = len(self.zones) > 0
        if not self._zones_calibrated:
            self.zones = ZoneSet.default_grid(self.protocol.zone_names)

        learned = LearnedRecognizer(config.action_model_file, config.action_metadata_file)
        self.recognition = RecognitionEngine(
            self.protocol,
            self.zones,
            window_frames=config.window_frames,
            fps=float(config.target_fps),
            learned=learned,
            learned_min_confidence=config.learned_min_confidence,
            prefer_learned=config.prefer_learned,
            stability_frames=config.stability_frames,
        )
        self.engine = ProtocolEngine(self.protocol)
        self.extractor = LandmarkExtractor(
            hands_enabled=config.hands_enabled,
            pose_enabled=config.pose_enabled,
            max_hands=config.max_hands,
            detection_confidence=config.detection_confidence,
            tracking_confidence=config.tracking_confidence,
            model_complexity=config.model_complexity,
        )
        static_quad = None
        rack_meta = self._load_rack_quad()
        if rack_meta is not None:
            static_quad = rack_meta
        self.rack_tracker = RackTracker(
            enabled=config.rack_marker_enabled,
            dictionary=config.rack_marker_dict,
            marker_ids=config.rack_marker_ids,
            static_quad=static_quad,
        )

        self.source = VideoSource(
            config.resolved_source(),
            width=config.frame_width,
            height=config.frame_height,
            fps=config.target_fps,
            flip_horizontal=config.flip_horizontal,
            loop_file=config.loop_video_file,
        )
        self.recorder = VideoRecorder(config.record_directory, fps=config.record_fps)
        self.streamer = VideoStreamer(
            config.stream_host,
            config.stream_port,
            quality=config.stream_quality,
            push_url=config.stream_push_url,
            fps=config.record_fps,
        )
        self.voice = VoiceAnnouncer(
            rate=config.voice_rate,
            volume=config.voice_volume,
            cooldown_s=config.voice_cooldown_s,
            enabled=config.voice_enabled,
        )
        self.logbook: Logbook | None = None

        # --- Round 2 subsystems ---------------------------------------
        self.quality = FrameQualityMonitor()
        self.rack_health = RackHealthManager()
        self.tracker = ObjectTracker()
        self.object_states = ObjectStateMachine()
        self.interactions = InteractionEngine()
        self.detector = build_detector(config)
        self.object_verifier = ObjectVerifier()
        self.fuser = EvidenceFuser()
        self.injector = FailureInjector()
        self.modes = ModeManager()
        self.supervisor = Supervisor()
        self.audit: AuditTrail | None = None
        self._last_decision = None
        self._last_quality = None
        self._last_rack_status = None
        self._last_tracks: list = []
        self._last_detections: list = []
        self._last_perception = None
        self._last_object_assessment = None
        self._last_relational_evidence = []
        self.relational_evidence = NestedContainerEvidence()
        self._detector_ran = False

        self.session_id = ""
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._frame_lock = threading.Lock()
        self._annotated: np.ndarray | None = None
        self._raw: np.ndarray | None = None
        self._events: list[ProtocolEvent] = []
        self._event_cursor = 0
        self._latencies: deque = deque(maxlen=60)
        self._frame_times: deque = deque(maxlen=60)
        self._frames = 0
        self._errors: list[str] = []
        self._overlay = OverlayState()
        self._commands: deque = deque()

    # ---------------------------------------------------------------- helpers

    def _load_rack_quad(self):
        import json

        path = self.config.zones_file.with_name("rack_quad.json")
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            quad = np.asarray(data["quad"], dtype=np.float32).reshape(4, 2)
            return quad
        except Exception as exc:
            LOGGER.warning("could not read rack quad: %s", exc)
            return None

    def _dispatch(self, events: list[ProtocolEvent]) -> None:
        for event in events:
            with self._lock:
                self._events.append(event)
                if len(self._events) > 500:
                    self._events = self._events[-500:]
            if self.logbook is not None:
                self.logbook.write_event(event)
            if self.config.voice_enabled:
                self.voice.announce_event(event)
            if event.severity in (Severity.WARNING, Severity.CRITICAL) or event.kind in (
                "step_completed",
                "session_completed",
            ):
                self._overlay.alert = event.message
                self._overlay.alert_severity = event.severity.value
                self._overlay.alert_until = time.monotonic() + (6.0 if event.severity is Severity.CRITICAL else 3.5)
            if self.on_event is not None:
                try:
                    self.on_event(event)
                except Exception as exc:  # pragma: no cover
                    LOGGER.debug("event callback failed: %s", exc)

    # -------------------------------------------------------------- lifecycle

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> PipelineStatus:
        if self.running:
            return self.snapshot()

        self.session_id = new_session_id()
        self._stop.clear()
        self._errors.clear()
        self._frames = 0
        self._event_cursor = 0
        with self._lock:
            self._events.clear()

        self.logbook = Logbook(
            self.config.log_directory, self.session_id, self.protocol.experiment, len(self.protocol)
        )
        self.logbook.write_note("perception", f"landmarks={self.extractor.describe()}")
        self.logbook.write_note("recognition", f"{self.recognition.tier} :: {self.recognition.tier_detail()}")
        self.logbook.write_note(
            "zones",
            f"{len(self.zones)} zones ({'calibrated' if self._zones_calibrated else 'AUTO-GENERATED - run CALIBRATE.bat'})",
            status="INFO" if self._zones_calibrated else "WARN",
        )

        self.audit = AuditTrail(
            self.config.log_directory / f"{self.session_id}_audit.jsonl",
            session_id=self.session_id,
        )
        self.audit.system("protocol_loaded", f"Protocol: {self.protocol.experiment}",
                          steps=len(self.protocol))
        self.audit.system("recognition", self.recognition.tier, detail=self.recognition.tier_detail())

        self.injector.reset()
        self.injector.on_change(self._on_fault_change)
        self.quality.reset()
        self.rack_health.reset()
        self.tracker.reset()
        self.object_states.reset()
        self.interactions.reset()
        self._last_tracks = []
        self._last_detections = []
        self._last_object_assessment = None
        self._last_relational_evidence = []
        self.relational_evidence.reset()

        detector_note = self.detector.describe()
        self.logbook.write_note(
            "objects", detector_note,
            status="INFO" if self.detector.available else "WARN",
        )
        self.audit.system("object_detector", detector_note,
                          available=self.detector.available,
                          **{k: v for k, v in self.detector.stats().items()
                             if k in ("providers", "labels", "input_size")})

        self.supervisor = Supervisor(grace_s=4.0)
        self.supervisor.register("pipeline", timeout_s=4.0, critical=True)
        self.supervisor.register("capture", timeout_s=5.0, critical=True,
                                 restart=self._restart_capture)
        self.supervisor.on_state_change(self._on_worker_change)
        self.supervisor.start()

        self.modes.request(Mode.MISSION, "operator started session")

        if self.config.voice_enabled:
            self.voice.start()

        if not self.source.start():
            self._errors.append(self.source.error)
            self.logbook.write_note("camera", self.source.error, status="ERROR")
            LOGGER.error("camera failed: %s", self.source.error)

        if self.config.stream_enabled:
            status = self.streamer.start()
            self.logbook.write_note(
                "stream",
                status.url if status.active else f"failed: {status.error}",
                status="INFO" if status.active else "ERROR",
            )
            if self.config.stream_target_ip:
                self.logbook.write_note("stream", f"target ground station: {self.config.stream_target_ip}")

        self.recognition.reset()
        self.engine = ProtocolEngine(self.protocol)
        self._dispatch(self.engine.start())

        self._thread = threading.Thread(target=self._run, name="har-pipeline", daemon=True)
        self._thread.start()
        return self.snapshot()

    def _run(self) -> None:
        recorder_started = False
        while not self._stop.is_set():
            frame = self.source.read(timeout=0.2)
            if frame is None:
                time.sleep(0.005)
                continue

            t0 = time.monotonic()
            self.supervisor.beat("pipeline")
            self.supervisor.beat("capture")

            # Faults are applied to the pipeline's *inputs*, so the code path
            # exercised under injection is exactly the production path.
            image = self.injector.apply(frame.image)
            if image is None:                       # simulated disconnection
                quality = self.quality.update(None)
                self._last_quality = quality
                self.modes.evaluate(camera_usable=False, rack_usable=False,
                                    critical_worker_fault=False)
                time.sleep(0.05)
                continue

            latency_penalty = self.injector.extra_latency_s
            if latency_penalty:
                time.sleep(latency_penalty)

            quality = self.quality.update(image)
            self._last_quality = quality

            if self.config.record_enabled and not recorder_started:
                path = self.recorder.start(self.session_id, image.shape[:2])
                recorder_started = True
                if self.logbook is not None:
                    self.logbook.write_note(
                        "recording",
                        str(path) if path else f"failed: {self.recorder.status().error}",
                        status="INFO" if path else "ERROR",
                    )

            try:
                rack = self.rack_tracker.update(image)
            except Exception as exc:  # pragma: no cover
                LOGGER.debug("rack tracking failed: %s", exc)
                rack = identity_frame(image.shape[1], image.shape[0])

            rack_status = self.rack_health.update(rack)
            self._last_rack_status = rack_status

            # Rack health gates validation only when zones are actually
            # calibrated. If the operator never calibrated, zone evidence was
            # never load-bearing -- the run is already flagged as degraded, and
            # halting it would punish a configuration we explicitly support.
            # With zones calibrated, a lost rack frame DOES mean zone membership
            # is meaningless, and continuing to validate would be unsound.
            rack_gate = rack_status.health.usable_for_zones or not self._zones_calibrated
            self.modes.evaluate(
                camera_usable=quality.usable,
                rack_usable=rack_gate,
                critical_worker_fault=self.supervisor.critical_fault,
            )

            try:
                result = self.extractor.process(image, frame.index, frame.timestamp)
                attach_rack_coords(result, rack)
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("perception failed: %s", exc)
                self._note_error(f"perception: {exc}")
                time.sleep(0.02)
                continue

            self._drain_commands()

            try:
                rec = self.recognition.process(result, self.engine.cursor, rack.confidence)
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("recognition failed: %s", exc)
                self._note_error(f"recognition: {exc}")
                rec = None

            # --- object detection (Tier 2, optional) ------------------------
            # Detection runs on every Nth frame; the tracker's constant-velocity
            # model covers the gaps. Feeding it an empty list between hits is
            # deliberate -- that is the same path an occlusion takes, and it is
            # already tested. DISABLE_MODEL takes the detector down with the
            # action model so the fault demonstrates a full Tier 2 -> Tier 0
            # fallback rather than a partial one.
            detections = []
            self._detector_ran = False
            if self.detector.available and not self.injector.model_disabled:
                interval = max(1, int(self.config.objects_interval))
                if self._frames % interval == 0:
                    detections = self.detector.detect(image)
                    self._detector_ran = True
            self._last_detections = detections

            # --- interaction reasoning (works with or without a detector) ---
            try:
                tracks = self.tracker.update(detections)
                self.object_states.update(tracks, [h.centroid_px for h in result.hands], self.zones, rack)
                fired = self.interactions.update(result, tracks, self.zones, rack)
                self._last_relational_evidence = self.relational_evidence.process(tracks, fired)
            except Exception as exc:                       # pragma: no cover
                LOGGER.debug("interaction engine failed: %s", exc)
                tracks, fired = [], []
            self._last_tracks = tracks
            self._last_perception = result

            if fired and self.audit is not None:
                for ev in fired[:6]:
                    self.audit.interaction(ev.type.value, ev.describe(), **ev.to_dict())

            # --- evidence fusion --------------------------------------------
            decision = None
            if rec is not None and rec.action is not None:
                decision = self._fuse(rec, quality, rack_status)
                self._last_decision = decision

            # Only an actionable verdict advances the protocol. UNCERTAIN and
            # NOT_OBSERVABLE are recorded but never mistaken for progress.
            if rec is not None and self.modes.mode.validates:
                actionable = decision.actionable if decision is not None else (rec.action is None)
                if rec.action is None or actionable:
                    events = self.engine.observe(
                        Observation(rec.action, rec.confidence, zone=rec.zone,
                                    hand=rec.hand, source=rec.source)
                    )
                    if events:
                        self._dispatch(events)
                elif decision is not None and self.audit is not None:
                    self.audit.action(
                        "not_accepted",
                        f"{rec.action}: {decision.verdict.value} - {decision.reason()}",
                        verdict=decision.verdict.value,
                        confidence=round(decision.confidence, 3),
                    )

            self._update_overlay(rec, rack)
            annotated = draw(image, result, rack, self.zones, self._overlay)

            with self._frame_lock:
                self._annotated = annotated
                self._raw = image

            if self.recorder.active:
                self.recorder.write(annotated if self.config.record_annotated else image)
            if self.streamer.active:
                self.streamer.publish(annotated)

            elapsed = time.monotonic() - t0
            self._latencies.append(elapsed * 1000.0)
            self._frame_times.append(time.monotonic())
            self._frames += 1

            if self.engine.completed:
                if self.logbook is not None:
                    self.logbook.write_note("session", "protocol complete - continuing to observe")
                # Keep streaming/recording; the operator decides when to stop.

    def _restart_capture(self) -> bool:
        try:
            self.source.stop()
        except Exception:
            pass
        return bool(self.source.start())

    def _on_fault_change(self, fault, active: bool) -> None:
        text = f"{'INJECTED' if active else 'CLEARED'}: {fault.label}"
        if self.audit is not None:
            self.audit.system("fault_injection", text,
                              fault=fault.value, active=active,
                              expected=fault.expected_response)
        if self.logbook is not None:
            self.logbook.write_note("failure_injection", f"{text} - expected: {fault.expected_response}",
                                    status="WARN" if active else "INFO")

    def _on_worker_change(self, worker, previous) -> None:
        if self.audit is not None:
            self.audit.system("worker_state", f"worker {worker.name}: {previous.value} -> {worker.state.value}",
                              worker=worker.name, state=worker.state.value, fault=worker.last_fault)
        if worker.state.value in ("faulted", "disabled") and self.logbook is not None:
            self.logbook.write_note("watchdog", f"{worker.name} {worker.state.value}: {worker.last_fault}",
                                    status="ERROR")

    def _note_error(self, message: str) -> None:
        with self._lock:
            if message not in self._errors:
                self._errors.append(message)
                if len(self._errors) > 20:
                    self._errors = self._errors[-20:]

    def _fuse(self, rec, quality, rack_status):
        """Assemble independent evidence for the recognised action.

        Each signal is added separately so the resulting explanation names the
        specific facts that supported (or undermined) the decision, rather than
        emitting a single opaque score.
        """
        ev = []

        source = Source.TEMPORAL_MODEL if rec.source == "learned" else Source.MOTION
        ev.append(self.fuser.evidence(
            source,
            f"{'temporal model' if rec.source == 'learned' else 'rule tier'} reports '{rec.action}'",
            rec.confidence,
        ))

        expected = self.engine.current_step
        if expected is not None and expected.zone:
            if rec.zone == expected.zone:
                ev.append(self.fuser.evidence(
                    Source.ZONE, f"hand in expected zone '{expected.zone}'", 0.95))
            elif rec.zone:
                ev.append(self.fuser.evidence(
                    Source.ZONE, f"hand in '{rec.zone}', expected '{expected.zone}'", 0.15))
            else:
                ev.append(self.fuser.evidence(
                    Source.ZONE, "hand not inside any calibrated zone", 0.30))

        # Object identity. This is the only channel that can say "you are
        # holding the wrong thing", so it is assembled even when the step's
        # motion evidence is already strong -- a correct gesture on the wrong
        # container is exactly the failure this exists to catch.
        if expected is not None:
            assessment = self.object_verifier.assess(
                expected.obj,
                self._last_tracks,
                [h.centroid_px for h in self._last_perception.hands]
                if self._last_perception is not None else [],
                detector_available=self.detector.available,
            )
            self._last_object_assessment = assessment
            object_evidence = assessment.as_evidence()
            if object_evidence is not None:
                ev.append(object_evidence)

        from aegis.fusion.interaction import EventType
        recent = {e.type for e in self.interactions.recent(2.5)}
        if EventType.GRIP_CLOSE in recent:
            ev.append(self.fuser.evidence(Source.GRIP, "grip closed within 2.5 s", 0.85))
        elif EventType.GRIP_OPEN in recent:
            ev.append(self.fuser.evidence(Source.GRIP, "grip opened within 2.5 s", 0.85))
        if EventType.ZONE_ENTER in recent:
            ev.append(self.fuser.evidence(Source.INTERACTION, "hand entered a zone recently", 0.75))

        ev.append(self.fuser.evidence(
            Source.RACK, rack_status.summary(), rack_status.evidence_weight))

        for relational in self._last_relational_evidence:
            if relational.action == rec.action:
                ev.append(Evidence(
                    Source.INTERACTION,
                    relational.label,
                    relational.score,
                    relational.weight,
                    {"action": relational.action},
                ))

        vetoes = camera_veto(quality) + self.rack_health.veto()
        return self.fuser.fuse(rec.action, ev, vetoes=vetoes,
                               quality_scale=quality.confidence_scale if quality else 1.0)

    def _update_overlay(self, rec, rack) -> None:
        step = self.engine.current_step
        done, total = self.engine.progress()
        self._overlay.instruction = self.engine.next_instruction
        self._overlay.step_label = (
            f"BLOCKED - STEP {step.id}" if (self.engine.blocked and step) else
            (f"STEP {step.id} / {total} - {step.name}" if step else "PROTOCOL COMPLETE")
        )
        self._overlay.progress = (done, total)
        self._overlay.tier = self.recognition.tier
        self._overlay.fps = self.measured_fps()
        self._overlay.confidence = rec.confidence if rec else 0.0
        self._overlay.rack_source = rack.source
        self._overlay.blocked = self.engine.blocked
        self._overlay.session_id = self.session_id
        self._overlay.recording = self.recorder.active
        self._overlay.streaming = self.streamer.active

    # ---------------------------------------------------------------- control

    def _drain_commands(self) -> None:
        while self._commands:
            try:
                command = self._commands.popleft()
            except IndexError:
                break
            if command == "acknowledge":
                self._dispatch(self.engine.acknowledge())
            elif command == "skip":
                self._dispatch(self.engine.manual_skip())
            elif command == "confirm":
                self._dispatch(self.engine.force_complete())
            elif command == "reset":
                self.engine = ProtocolEngine(self.protocol)
                self.recognition.reset()
                self._dispatch(self.engine.start())

    def acknowledge(self) -> None:
        self._commands.append("acknowledge")

    def manual_skip(self) -> None:
        self._commands.append("skip")

    def confirm_step(self) -> None:
        self._commands.append("confirm")

    def reset_protocol(self) -> None:
        self._commands.append("reset")

    def inject_fault(self, fault) -> bool:
        """Toggle a fault. Returns whether it is now active."""
        return self.injector.toggle(fault)

    def clear_faults(self) -> None:
        self.injector.clear_all()

    def set_markers_visible(self, visible: bool) -> None:
        self._overlay.show_markers = visible

    def last_explanation(self) -> str:
        return self._last_decision.explain() if self._last_decision else "no decision yet"

    def toggle_recording(self) -> bool:
        if self.recorder.active:
            status = self.recorder.stop()
            if self.logbook:
                self.logbook.write_note("recording", f"stopped: {status.frames} frames -> {status.path}")
            return False
        with self._frame_lock:
            shape = self._raw.shape[:2] if self._raw is not None else (self.config.frame_height, self.config.frame_width)
        path = self.recorder.start(f"{self.session_id}_part{int(time.time())%10000}", shape)
        if self.logbook:
            self.logbook.write_note("recording", f"started: {path}")
        return path is not None

    def toggle_streaming(self) -> bool:
        if self.streamer.active:
            self.streamer.stop()
            if self.logbook:
                self.logbook.write_note("stream", "stopped")
            return False
        status = self.streamer.start()
        if self.logbook:
            self.logbook.write_note("stream", status.url if status.active else f"failed: {status.error}")
        return status.active

    def toggle_voice(self) -> bool:
        self.voice.enabled = not self.voice.enabled and self.voice.available
        if self.voice.enabled:
            self.voice.start()
            self.voice.say("Voice guidance enabled.", force=True)
        return self.voice.enabled

    # ---------------------------------------------------------------- readout

    def measured_fps(self) -> float:
        times = list(self._frame_times)
        if len(times) < 2:
            return 0.0
        span = times[-1] - times[0]
        return (len(times) - 1) / span if span > 1e-6 else 0.0

    def latest_frame(self) -> np.ndarray:
        with self._frame_lock:
            if self._annotated is not None:
                return self._annotated
        message = "CAMERA UNAVAILABLE" if self.source.error else "WAITING FOR SIGNAL"
        return placeholder(self.config.frame_width // 2, self.config.frame_height // 2, message)

    def drain_events(self) -> list[ProtocolEvent]:
        """Events not yet consumed by the GUI."""
        with self._lock:
            new = self._events[self._event_cursor :]
            self._event_cursor = len(self._events)
        return new

    def snapshot(self) -> PipelineStatus:
        stream = self.streamer.status()
        rec_status = self.recorder.status()
        latency = float(np.mean(self._latencies)) if self._latencies else 0.0
        rec = self.recognition.last_raw
        with self._lock:
            errors = list(self._errors)
        return PipelineStatus(
            running=self.running,
            session_id=self.session_id,
            camera_ok=self.source.opened,
            camera_desc=self.source.describe(),
            camera_error=self.source.error,
            perception=self.extractor.describe(),
            tier=self.recognition.tier,
            tier_detail=self.recognition.tier_detail(),
            rack_source=self._overlay.rack_source or "-",
            rack_confidence=0.0,
            fps=self.measured_fps(),
            latency_ms=latency,
            frames=self._frames,
            zones_calibrated=self._zones_calibrated,
            recording=rec_status.active,
            record_path=rec_status.path,
            streaming=stream.active,
            stream_url=stream.url,
            stream_clients=stream.clients,
            voice_ok=self.voice.enabled and self.voice.available,
            voice_error=self.voice.error,
            log_path=str(self.logbook.text_path) if self.logbook else "",
            last_action=(rec.action or "-") if rec else "-",
            last_confidence=(rec.confidence if rec else 0.0),
            errors=errors,
            mode=self.modes.mode.value,
            camera_health=(self._last_quality.state.value if self._last_quality else "nominal"),
            camera_reasons=(list(self._last_quality.reasons) if self._last_quality else []),
            rack_health=(self._last_rack_status.health.value if self._last_rack_status else "red"),
            rack_summary=(self._last_rack_status.summary() if self._last_rack_status else ""),
            verdict=(self._last_decision.verdict.value if self._last_decision else ""),
            verdict_reason=(self._last_decision.reason() if self._last_decision else ""),
            explanation=(self._last_decision.explain() if self._last_decision else ""),
            tracked_objects=len(self.tracker.confirmed_tracks()),
            interaction_events=len(self.interactions.events),
            workers_ok=self.supervisor.all_healthy,
            worker_summary=self.supervisor.summary(),
            injected_faults=[f.label for f in self.injector.active_faults()],
            audit_head=(self.audit.head[:16] if self.audit else ""),
            detector_ok=self.detector.available,
            detector_desc=self.detector.describe(),
            detector_latency_ms=getattr(self.detector, "mean_latency_ms", 0.0),
            object_match=(self._last_object_assessment.match.value
                          if self._last_object_assessment else ""),
            object_summary=(self._last_object_assessment.label
                            if self._last_object_assessment else ""),
            detected_labels=sorted({t.label for t in self.tracker.confirmed_tracks()}),
            audit_entries=(len(self.audit.entries) if self.audit else 0),
        )

    def protocol_snapshot(self) -> dict:
        return self.engine.snapshot()

    # ------------------------------------------------------------------ stop

    def stop(self) -> Path | None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=4.0)
        self._thread = None

        self.supervisor.stop()
        self.modes.request(Mode.STANDBY, "session stopped")
        rec_status = self.recorder.stop()
        self.streamer.stop()
        self.source.stop()

        report: Path | None = None
        if self.logbook is not None:
            extras = {
                "Frames": self._frames,
                "Mean latency": f"{float(np.mean(self._latencies)) if self._latencies else 0:.1f} ms",
                "Recognition": f"{self.recognition.tier}",
                "Video": rec_status.path or "not recorded",
                "Voice alerts": self.voice.spoken_count,
                "Interaction events": len(self.interactions.events),
                "Faults injected": len(self.injector.history),
                "Worker faults": len(self.supervisor.faulted()),
            }
            if self.audit is not None:
                ok, bad, message = self.audit.verify()
                extras["Audit chain"] = f"{message}" if ok else f"BROKEN at entry {bad}: {message}"
                extras["Audit head"] = self.audit.close({"verdict_source": "session_end"})[:32]
                self.audit = None
            report = self.logbook.finalise(self.engine.snapshot(), extras)
            self.logbook = None

        self.voice.stop()
        try:
            self.extractor.close()
        except Exception:
            pass
        return report
