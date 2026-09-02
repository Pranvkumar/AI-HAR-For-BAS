"""Tests for the Round-2 safety and operations layer.

Covers failure injection, the watchdog supervisor, rack-localisation health, the
hash-chained audit trail and the operating-mode state machine. All hardware-free.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

cv2 = pytest.importorskip("cv2")

from aegis.outputs.audit import (
    AuditTrail, EventLevel, GENESIS, file_checksum, verify_file, write_checksums,
)
from aegis.perception.quality import FrameQualityMonitor, HealthState
from aegis.perception.rack_health import RackHealth, RackHealthManager, RackMode
from aegis.safety.failure_injection import DEMO_SEQUENCE, FailureInjector, FaultType
from aegis.safety.modes import Mode, ModeManager
from aegis.safety.watchdog import Supervisor, WorkerState


def textured(w=320, h=240, level=128):
    rng = np.random.default_rng(1)
    img = rng.integers(level - 50, level + 50, (h, w, 3), dtype=np.uint8)
    for x in range(0, w, 14):
        img[:, x:x + 3] = min(255, level + 95)
    return img


# ========================================================= failure injection

def test_injector_starts_clean():
    inj = FailureInjector()
    assert not inj.any_active
    frame = textured()
    assert inj.apply(frame) is frame, "no fault must be a pass-through"


def test_drop_camera_returns_none_like_a_real_failure():
    """The pipeline must not be able to distinguish injection from reality."""
    inj = FailureInjector()
    inj.inject(FaultType.DROP_CAMERA)
    assert inj.apply(textured()) is None


def test_occlusion_makes_the_quality_monitor_declare_unusable():
    """End-to-end: injected fault -> real detector -> correct verdict."""
    inj = FailureInjector()
    monitor = FrameQualityMonitor()
    for _ in range(8):
        monitor.update(textured())
    assert monitor.update(textured()).state is HealthState.NOMINAL

    inj.inject(FaultType.OCCLUDE_LENS, intensity=1.0)
    for _ in range(10):
        q = monitor.update(inj.apply(textured()))
    assert q.state is HealthState.UNUSABLE
    assert q.confidence_scale == 0.0


def test_dim_lighting_degrades_but_does_not_suspend():
    inj = FailureInjector()
    monitor = FrameQualityMonitor()
    inj.inject(FaultType.DIM_LIGHTING, intensity=0.85)
    for _ in range(10):
        q = monitor.update(inj.apply(textured()))
    assert q.state is not HealthState.NOMINAL
    assert q.brightness < 0.25


def test_motion_blur_is_detected_as_blur():
    """Blur is caught by a relative collapse against the scene's own baseline.

    An absolute Laplacian threshold cannot do this alone: a finely textured
    scene stays numerically "sharp" even when heavily smeared, so the monitor
    learns what this camera normally looks like first.
    """
    inj = FailureInjector()
    monitor = FrameQualityMonitor()
    for _ in range(20):                       # establish the clean baseline
        monitor.update(textured())
    assert monitor.update(textured()).state is HealthState.NOMINAL

    inj.inject(FaultType.MOTION_BLUR, intensity=1.0)
    for _ in range(10):
        q = monitor.update(inj.apply(textured()))
    assert q.state is not HealthState.NOMINAL
    assert any("blur" in r or "focus" in r for r in q.reasons), q.reasons


def test_freeze_camera_repeats_one_frame():
    inj = FailureInjector()
    inj.inject(FaultType.FREEZE_CAMERA)
    first = inj.apply(textured(level=100))
    second = inj.apply(textured(level=200))
    assert np.array_equal(first, second), "a frozen feed must not change"


def test_rotate_camera_preserves_frame_shape():
    inj = FailureInjector()
    inj.inject(FaultType.ROTATE_CAMERA)
    frame = textured()
    out = inj.apply(frame)
    assert out.shape == frame.shape
    assert not np.array_equal(out, frame)


def test_hide_markers_blanks_the_margins():
    inj = FailureInjector()
    inj.inject(FaultType.HIDE_MARKERS)
    out = inj.apply(textured())
    h, w = out.shape[:2]
    assert out[: int(h * 0.1), :].std() < 5, "top margin should be flat"
    assert out[h // 2, w // 2].sum() > 0, "centre must remain visible"


def test_subsystem_faults_expose_flags():
    inj = FailureInjector()
    assert not inj.model_disabled and not inj.voice_disabled
    inj.inject(FaultType.DISABLE_MODEL)
    inj.inject(FaultType.DISABLE_VOICE)
    inj.inject(FaultType.SLOW_PIPELINE, intensity=0.5)
    assert inj.model_disabled and inj.voice_disabled
    assert inj.extra_latency_s > 0


def test_faults_compose_without_error():
    """Degradation must compose, not collapse into an unhandled state."""
    inj = FailureInjector()
    inj.inject(FaultType.DIM_LIGHTING, 0.6)
    inj.inject(FaultType.MOTION_BLUR, 0.6)
    inj.inject(FaultType.HIDE_MARKERS)
    out = inj.apply(textured())
    assert out is not None and out.shape == (240, 320, 3)
    assert len(inj.active_faults()) == 3


def test_toggle_and_clear():
    inj = FailureInjector()
    assert inj.toggle(FaultType.DIM_LIGHTING) is True
    assert inj.toggle(FaultType.DIM_LIGHTING) is False
    inj.inject(FaultType.OCCLUDE_LENS)
    inj.clear_all()
    assert not inj.any_active
    assert all(r.stopped is not None for r in inj.history)


def test_every_fault_declares_its_expected_response():
    """The GUI shows this beside the fault so a reviewer can check the claim."""
    for fault in FaultType:
        assert fault.label and fault.expected_response


def test_injection_history_is_reportable():
    inj = FailureInjector()
    inj.inject(FaultType.DIM_LIGHTING)
    inj.clear(FaultType.DIM_LIGHTING)
    report = inj.report()
    assert len(report) == 1
    assert report[0]["fault"] == "dim_lighting"
    assert report[0]["active"] is False
    assert "expected" in report[0]


def test_change_listener_fires():
    inj = FailureInjector()
    seen = []
    inj.on_change(lambda f, active: seen.append((f, active)))
    inj.inject(FaultType.DIM_LIGHTING)
    inj.clear(FaultType.DIM_LIGHTING)
    assert seen == [(FaultType.DIM_LIGHTING, True), (FaultType.DIM_LIGHTING, False)]


def test_demo_sequence_is_ordered_and_valid():
    assert len(DEMO_SEQUENCE) >= 5
    for fault, seconds in DEMO_SEQUENCE:
        assert isinstance(fault, FaultType) and seconds > 0


# =================================================================== watchdog

def test_healthy_worker_stays_healthy():
    sup = Supervisor(grace_s=0.0)
    sup.register("camera", timeout_s=1.0)
    sup.beat("camera")
    sup.check()
    assert sup.workers["camera"].state is WorkerState.HEALTHY
    assert sup.all_healthy


def test_silent_worker_is_declared_faulted():
    sup = Supervisor(grace_s=0.0)
    w = sup.register("recorder", timeout_s=0.05)
    sup.beat("recorder")
    time.sleep(0.13)
    sup.check()
    assert w.state is WorkerState.FAULTED
    assert "no heartbeat" in w.last_fault
    assert not sup.all_healthy


def test_wedged_worker_is_caught_even_though_thread_is_alive():
    """A pull heartbeat catches a blocked thread; is_alive() would not."""
    sup = Supervisor(grace_s=0.0)
    w = sup.register("pose", timeout_s=0.05)
    sup.beat("pose")
    time.sleep(0.15)                       # thread alive but stuck
    sup.check()
    assert w.state is WorkerState.FAULTED


def test_faulted_worker_is_restarted_and_recovers():
    calls = []

    def restart():
        calls.append(1)
        return True

    sup = Supervisor(grace_s=0.0)
    w = sup.register("streamer", timeout_s=0.05, restart=restart)
    sup.beat("streamer")
    time.sleep(0.13)
    sup.check()
    assert calls, "restart callback should have fired"
    sup.beat("streamer")
    assert w.state is WorkerState.HEALTHY


def test_restart_budget_is_enforced():
    """A repeatedly failing worker must be left down, not restarted forever."""
    sup = Supervisor(grace_s=0.0)
    w = sup.register("flaky", timeout_s=0.02, restart=lambda: False, max_restarts=2)
    for _ in range(6):
        time.sleep(0.05)
        sup.check()
    assert w.restarts <= 2
    assert w.state in (WorkerState.DISABLED, WorkerState.FAULTED)


def test_critical_worker_fault_is_surfaced():
    sup = Supervisor(grace_s=0.0)
    sup.register("camera", timeout_s=0.02, critical=True)
    sup.register("voice", timeout_s=0.02, critical=False)
    time.sleep(0.06)
    sup.check()
    assert sup.critical_fault


def test_deliberate_stop_is_not_a_fault():
    sup = Supervisor(grace_s=0.0)
    sup.register("recorder", timeout_s=0.02)
    sup.stopped("recorder")
    time.sleep(0.06)
    sup.check()
    assert sup.workers["recorder"].state is WorkerState.STOPPED
    assert not sup.faulted()


def test_self_reported_fault():
    sup = Supervisor(grace_s=0.0)
    sup.register("detector")
    sup.report_fault("detector", "onnx session died")
    assert sup.workers["detector"].state is WorkerState.FAULTED
    assert "onnx" in sup.summary()


def test_snapshot_shape():
    sup = Supervisor(grace_s=0.0)
    sup.register("camera")
    sup.beat("camera")
    snap = sup.snapshot()
    assert "workers" in snap and snap["workers"][0]["name"] == "camera"


# ================================================================ rack health

class FakeRack:
    def __init__(self, source, confidence=0.95, corners=None, roll=0.0):
        self.source = source
        self.confidence = confidence
        self.corners_px = corners if corners is not None else np.array(
            [[10, 10], [200, 10], [200, 150], [10, 150]], np.float32)
        self.roll_deg = roll


def test_live_markers_are_green():
    m = RackHealthManager()
    for _ in range(6):
        s = m.update(FakeRack("aruco", 0.95))
    assert s.health is RackHealth.GREEN
    assert s.locked and s.evidence_weight == 1.0
    assert m.veto() == []


def test_identity_frame_is_red_and_vetoes():
    m = RackHealthManager()
    s = m.update(FakeRack("identity", 0.25))
    assert s.health is RackHealth.RED
    assert s.evidence_weight == 0.0
    assert m.veto(), "an unlocalised rack must veto zone evidence"


def test_brief_hold_stays_green_then_degrades():
    m = RackHealthManager(hold_yellow_s=0.05, hold_red_s=0.2)
    m.update(FakeRack("aruco", 0.95))
    assert m.update(FakeRack("aruco_hold", 0.9)).health is RackHealth.GREEN
    time.sleep(0.08)
    assert m.update(FakeRack("aruco_hold", 0.9)).health is RackHealth.YELLOW
    time.sleep(0.25)
    s = m.update(FakeRack("aruco_hold", 0.9))
    assert s.health is RackHealth.RED
    assert any("stale" in r for r in s.reasons)


def test_static_calibration_is_yellow_not_green():
    """A static quad is only valid if the camera has not moved -- we cannot know."""
    m = RackHealthManager()
    s = m.update(FakeRack("static", 0.8))
    assert s.health is RackHealth.YELLOW
    assert 0 < s.evidence_weight < 1.0


def test_jittering_quad_is_flagged_unstable():
    m = RackHealthManager()
    rng = np.random.default_rng(0)
    for _ in range(12):
        noisy = np.array([[10, 10], [200, 10], [200, 150], [10, 150]], np.float32)
        noisy += rng.normal(0, 30, noisy.shape).astype(np.float32)
        s = m.update(FakeRack("aruco", 0.95, corners=noisy))
    assert s.stability < 0.5
    assert s.health is RackHealth.YELLOW


def test_health_transitions_are_recorded():
    m = RackHealthManager()
    m.update(FakeRack("aruco", 0.95))
    m.update(FakeRack("identity", 0.2))
    assert m.transitions()
    assert m.transitions()[-1]["to"] == "red"


# ================================================================ audit chain

def test_chain_verifies_when_untouched():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.jsonl"
        trail = AuditTrail(path, session_id="s1")
        trail.protocol("step_completed", "Step 1 verified", step=1, confidence=0.91)
        trail.perception("frame_scored", "Frame nominal", brightness=0.42)
        trail.close({"verdict": "PASS"})

        ok, bad, msg = verify_file(path)
        assert ok, msg
        assert bad is None


def test_first_entry_links_to_genesis():
    with tempfile.TemporaryDirectory() as tmp:
        trail = AuditTrail(Path(tmp) / "a.jsonl", session_id="s")
        assert trail.entries[0].prev_hash == GENESIS


def test_each_entry_links_to_the_previous():
    with tempfile.TemporaryDirectory() as tmp:
        trail = AuditTrail(Path(tmp) / "a.jsonl", session_id="s")
        trail.action("recognised", "grasp")
        trail.action("recognised", "insert")
        for i in range(1, len(trail.entries)):
            assert trail.entries[i].prev_hash == trail.entries[i - 1].entry_hash


def test_editing_a_message_breaks_the_chain():
    """The property that makes the log evidence rather than a claim."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.jsonl"
        trail = AuditTrail(path, session_id="s1")
        trail.protocol("step_skipped", "Step 3 was skipped")
        trail.protocol("step_completed", "Step 4 verified")
        trail.close()

        lines = path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[1])
        tampered["message"] = "Step 3 was completed"      # falsify the record
        lines[1] = json.dumps(tampered)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        ok, bad, msg = verify_file(path)
        assert not ok
        assert bad == 1
        assert "hash" in msg or "modified" in msg


def test_deleting_an_entry_breaks_the_chain():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.jsonl"
        trail = AuditTrail(path, session_id="s1")
        for i in range(4):
            trail.action("recognised", f"action {i}")
        trail.close()

        lines = path.read_text(encoding="utf-8").splitlines()
        del lines[2]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        ok, bad, _ = verify_file(path)
        assert not ok and bad is not None


def test_event_levels_are_counted():
    with tempfile.TemporaryDirectory() as tmp:
        trail = AuditTrail(Path(tmp) / "a.jsonl", session_id="s")
        trail.perception("p", "x")
        trail.interaction("i", "x")
        trail.action("a", "x")
        trail.protocol("pr", "x")
        counts = trail.counts()
        for level in (EventLevel.PERCEPTION, EventLevel.INTERACTION,
                      EventLevel.ACTION, EventLevel.PROTOCOL):
            assert counts.get(level.value, 0) >= 1


def test_head_hash_changes_with_every_entry():
    with tempfile.TemporaryDirectory() as tmp:
        trail = AuditTrail(Path(tmp) / "a.jsonl", session_id="s")
        first = trail.head
        trail.action("x", "y")
        assert trail.head != first


def test_checksums_for_model_provenance():
    with tempfile.TemporaryDirectory() as tmp:
        model = Path(tmp) / "action_model.onnx"
        model.write_bytes(b"fake onnx payload")
        digest = file_checksum(model)
        assert len(digest) == 64

        sums = write_checksums([model], Path(tmp) / "SHA256SUMS")
        content = sums.read_text(encoding="utf-8")
        assert digest in content and "action_model.onnx" in content


def test_verify_reports_a_missing_file():
    ok, _, msg = verify_file("/nonexistent/audit.jsonl")
    assert not ok and "no audit file" in msg


# ============================================================ operating modes

def test_starts_in_standby():
    m = ModeManager()
    assert m.mode is Mode.STANDBY
    assert not m.mode.validates


def test_legal_transition_is_accepted():
    m = ModeManager()
    change = m.request(Mode.MISSION, "operator started session")
    assert change is not None
    assert m.mode is Mode.MISSION
    assert m.mode.validates and m.mode.records


def test_illegal_transition_is_refused():
    """Calibration must not jump straight to a mission run."""
    m = ModeManager()
    m.request(Mode.CALIBRATION, "calibrating")
    assert m.request(Mode.MISSION, "skip ahead") is None
    assert m.mode is Mode.CALIBRATION


def test_safe_mode_does_not_validate():
    m = ModeManager()
    m.request(Mode.MISSION, "start")
    m.request(Mode.SAFE, "camera lost")
    assert m.mode is Mode.SAFE
    assert not m.mode.validates, "SAFE must never advance the protocol"


def test_unusable_camera_drops_to_safe_automatically():
    m = ModeManager()
    m.request(Mode.MISSION, "start")
    change = m.evaluate(camera_usable=False, rack_usable=True, critical_worker_fault=False)
    assert change is not None and change.automatic
    assert m.mode is Mode.SAFE
    assert "camera" in change.reason


def test_unlocalised_rack_drops_to_safe():
    m = ModeManager()
    m.request(Mode.MISSION, "start")
    m.evaluate(camera_usable=True, rack_usable=False, critical_worker_fault=False)
    assert m.mode is Mode.SAFE


def test_critical_worker_fault_drops_to_safe():
    m = ModeManager()
    m.request(Mode.MISSION, "start")
    m.evaluate(camera_usable=True, rack_usable=True, critical_worker_fault=True)
    assert m.mode is Mode.SAFE


def test_recovery_returns_to_mission():
    m = ModeManager()
    m.request(Mode.MISSION, "start")
    m.evaluate(camera_usable=False, rack_usable=True, critical_worker_fault=False)
    assert m.mode is Mode.SAFE
    m.evaluate(camera_usable=True, rack_usable=True, critical_worker_fault=False)
    assert m.mode is Mode.MISSION


def test_mode_changes_are_logged_with_reasons():
    m = ModeManager()
    m.request(Mode.MISSION, "operator started session")
    m.request(Mode.SAFE, "camera lost", automatic=True)
    assert len(m.history) == 2
    assert "operator" in m.history[0].describe()
    assert "auto" in m.history[1].describe()


def test_listener_fires_on_change():
    m = ModeManager()
    seen = []
    m.on_change(seen.append)
    m.request(Mode.MISSION, "start")
    assert seen and seen[0].to is Mode.MISSION


def test_snapshot_lists_allowed_next_modes():
    m = ModeManager()
    snap = m.snapshot()
    assert snap["mode"] == "standby"
    assert "mission" in snap["allowed_next"]
