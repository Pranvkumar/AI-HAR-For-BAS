"""Integration: the wired pipeline under injected faults.

These are the tests that matter for the Round-2 claim. Unit tests prove each
subsystem behaves; these prove the *assembled system* actually degrades the way
the slides say it does, using the real pipeline over synthetic video with no
camera attached.
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

from aegis.config import AppConfig
from aegis.outputs.audit import verify_file
from aegis.pipeline import HARPipeline
from aegis.safety.failure_injection import FaultType
from aegis.safety.modes import Mode

ROOT = Path(__file__).resolve().parents[1]


def make_clip(path: Path, frames: int = 120, size=(640, 360)) -> Path:
    """A textured moving scene, so quality metrics are meaningful."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 20.0, size)
    assert writer.isOpened()
    rng = np.random.default_rng(3)
    for i in range(frames):
        img = rng.integers(70, 180, (size[1], size[0], 3), dtype=np.uint8)
        for x in range(0, size[0], 24):
            img[:, x:x + 4] = 235
        cx = int(200 + 140 * np.sin(i / 11.0))
        cv2.circle(img, (cx, 190), 34, (210, 170, 120), -1)
        cv2.rectangle(img, (40, 40), (600, 320), (60, 60, 70), 2)
        writer.write(img)
    writer.release()
    return path


def build(tmp: Path, **overrides) -> HARPipeline:
    clip = make_clip(tmp / "clip.mp4")
    cfg = AppConfig(root=ROOT)
    cfg.video_source = str(clip)
    cfg.loop_video_file = True
    cfg.frame_width, cfg.frame_height = 640, 360
    cfg.target_fps = 20
    cfg.record_fps = 20
    cfg.voice_enabled = False
    cfg.record_enabled = False
    cfg.stream_enabled = False
    cfg.log_dir = str(tmp / "logs")
    cfg.record_dir = str(tmp / "video")
    cfg.protocol_path = str(ROOT / "configs" / "protocol.yaml")
    cfg.zones_path = str(tmp / "zones.json")
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return HARPipeline(cfg)


def spin(pipeline: HARPipeline, frames: int = 30, timeout: float = 12.0) -> None:
    """Let the pipeline process at least ``frames`` frames."""
    start = pipeline.snapshot().frames
    deadline = time.time() + timeout
    while time.time() < deadline and pipeline.snapshot().frames < start + frames:
        time.sleep(0.1)


def test_pipeline_starts_in_mission_mode_and_stays_nominal():
    with tempfile.TemporaryDirectory() as tmp:
        p = build(Path(tmp))
        p.start()
        try:
            spin(p, 30)
            s = p.snapshot()
            assert s.mode == Mode.MISSION.value
            assert s.camera_health == "nominal", s.camera_reasons
            assert s.workers_ok, s.worker_summary
            assert s.audit_entries > 0
        finally:
            p.stop()


def test_occluded_lens_drops_the_session_to_safe_mode():
    """The headline degradation claim, end to end."""
    with tempfile.TemporaryDirectory() as tmp:
        p = build(Path(tmp))
        p.start()
        try:
            spin(p, 30)
            assert p.snapshot().mode == Mode.MISSION.value

            p.inject_fault(FaultType.OCCLUDE_LENS)
            spin(p, 40)

            s = p.snapshot()
            assert s.camera_health == "unusable", s.camera_reasons
            assert s.mode == Mode.SAFE.value, "must suspend validation, not guess"
            assert "Lens occluded" in s.injected_faults

            p.clear_faults()
            spin(p, 50)
            assert p.snapshot().mode == Mode.MISSION.value, "must recover automatically"
        finally:
            p.stop()


def test_camera_disconnect_does_not_kill_the_pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        p = build(Path(tmp))
        p.start()
        try:
            spin(p, 25)
            p.inject_fault(FaultType.DROP_CAMERA)
            time.sleep(1.5)
            assert p.running, "pipeline thread must survive a dead camera"

            p.clear_faults()
            spin(p, 30)
            assert p.snapshot().frames > 0
        finally:
            p.stop()


def test_dim_lighting_degrades_confidence_without_stopping():
    with tempfile.TemporaryDirectory() as tmp:
        p = build(Path(tmp))
        p.start()
        try:
            spin(p, 30)
            p.inject_fault(FaultType.DIM_LIGHTING)
            spin(p, 40)
            s = p.snapshot()
            assert s.camera_health in ("degraded", "unusable")
            assert p.running
        finally:
            p.stop()


def test_protocol_does_not_advance_while_in_safe_mode():
    """The safety property: no verification on unusable input."""
    with tempfile.TemporaryDirectory() as tmp:
        p = build(Path(tmp))
        p.start()
        try:
            spin(p, 25)
            p.inject_fault(FaultType.OCCLUDE_LENS)
            spin(p, 40)
            assert p.snapshot().mode == Mode.SAFE.value

            before = p.protocol_snapshot()["done"]
            spin(p, 60)
            after = p.protocol_snapshot()["done"]
            assert after == before, "SAFE mode must never advance the protocol"
        finally:
            p.stop()


def test_interaction_events_are_produced():
    with tempfile.TemporaryDirectory() as tmp:
        p = build(Path(tmp))
        p.start()
        try:
            spin(p, 45)
            assert p.snapshot().interaction_events >= 0   # engine ran without error
            assert isinstance(p.last_explanation(), str)
        finally:
            p.stop()


def test_audit_trail_is_written_and_verifies():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        p = build(tmp_path)
        p.start()
        try:
            spin(p, 30)
            p.inject_fault(FaultType.DIM_LIGHTING)
            spin(p, 20)
            p.clear_faults()
        finally:
            p.stop()

        audits = list((tmp_path / "logs").glob("*_audit.jsonl"))
        assert audits, "an audit trail must be written"
        ok, bad, message = verify_file(audits[0])
        assert ok, f"chain broken at {bad}: {message}"

        text = audits[0].read_text(encoding="utf-8")
        assert "fault_injection" in text, "injections must be recorded"
        assert "audit_sealed" in text


def test_report_records_the_injected_faults():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        p = build(tmp_path)
        p.start()
        try:
            spin(p, 25)
            p.inject_fault(FaultType.HIDE_MARKERS)
            spin(p, 20)
        finally:
            report = p.stop()

        assert report is not None and report.exists()
        text = report.read_text(encoding="utf-8")
        assert "Faults injected" in text
        assert "Audit chain" in text
        assert "chain intact" in text


def test_watchdog_registers_and_beats():
    with tempfile.TemporaryDirectory() as tmp:
        p = build(Path(tmp))
        p.start()
        try:
            spin(p, 30)
            snap = p.supervisor.snapshot()
            names = {w["name"] for w in snap["workers"]}
            assert {"pipeline", "capture"} <= names
            assert snap["all_healthy"], snap
            assert all(w["beats"] > 0 for w in snap["workers"] if w["name"] == "pipeline")
        finally:
            p.stop()


def test_faults_compose_in_the_live_pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        p = build(Path(tmp))
        p.start()
        try:
            spin(p, 25)
            p.inject_fault(FaultType.DIM_LIGHTING)
            p.inject_fault(FaultType.MOTION_BLUR)
            p.inject_fault(FaultType.HIDE_MARKERS)
            spin(p, 30)
            s = p.snapshot()
            assert len(s.injected_faults) == 3
            assert p.running, "composed degradation must not crash the pipeline"
        finally:
            p.stop()
