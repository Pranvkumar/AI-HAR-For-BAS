"""Round-2 module tests: camera health, evidence fusion, tracking, interaction.

All hardware-free. Synthetic frames and synthetic detections only.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

cv2 = pytest.importorskip("cv2")

from aegis.fusion.evidence import (
    DEFAULT_WEIGHTS, Evidence, EvidenceFuser, Source, Verdict, camera_veto, rack_veto,
)
from aegis.fusion.interaction import EventType, InteractionEngine
from aegis.perception.landmarks import HandObservation, PerceptionResult
from aegis.perception.quality import FrameQualityMonitor, HealthState
from aegis.perception.tracking import (
    Detection, ObjectState, ObjectStateMachine, ObjectTracker, iou,
)
from aegis.perception.zones import Zone, ZoneSet


# =============================================================== frame quality

def textured(w=320, h=240, level=128):
    """A frame with real texture, so sharpness metrics are meaningful."""
    rng = np.random.default_rng(0)
    img = rng.integers(max(0, level - 55), min(255, level + 55), (h, w, 3), dtype=np.uint8)
    for x in range(0, w, 16):
        img[:, x:x + 3] = min(255, level + 90)
    return img


def test_nominal_frame_is_nominal():
    m = FrameQualityMonitor()
    for _ in range(8):
        q = m.update(textured())
    assert q.state is HealthState.NOMINAL, q.reasons
    assert q.usable and q.confidence_scale == 1.0


def test_dark_frame_is_flagged():
    m = FrameQualityMonitor()
    for _ in range(8):
        q = m.update(np.full((240, 320, 3), 6, np.uint8))
    assert q.state is not HealthState.NOMINAL
    assert any("illumination" in r or "blur" in r or "contrast" in r for r in q.reasons)
    assert q.confidence_scale < 1.0


def test_blurred_frame_is_flagged():
    m = FrameQualityMonitor()
    blurred = cv2.GaussianBlur(textured(), (31, 31), 0)
    for _ in range(8):
        q = m.update(blurred)
    assert q.state is not HealthState.NOMINAL
    assert any("blur" in r or "focus" in r for r in q.reasons)


def test_occluded_lens_is_unusable():
    m = FrameQualityMonitor()
    for _ in range(8):
        q = m.update(np.zeros((240, 320, 3), np.uint8))
    assert q.state is HealthState.UNUSABLE
    assert q.confidence_scale == 0.0


def test_missing_frames_become_unusable_after_timeout():
    m = FrameQualityMonitor()
    m.update(textured())
    m._last_good -= 5.0                      # simulate a stalled camera
    for _ in range(6):
        q = m.update(None)
    assert q.state is HealthState.UNUSABLE
    assert any("no fresh frame" in r for r in q.reasons)


def test_single_bad_frame_does_not_flip_state():
    """Debounce: one dark frame in a good stream must not suspend validation."""
    m = FrameQualityMonitor()
    for _ in range(10):
        m.update(textured())
    q = m.update(np.zeros((240, 320, 3), np.uint8))
    assert q.state is not HealthState.UNUSABLE


# ============================================================ evidence fusion

def test_strong_agreement_verifies():
    f = EvidenceFuser()
    ev = [
        f.evidence(Source.ZONE, "hand in sample_tray", 0.97),
        f.evidence(Source.TEMPORAL_MODEL, "model predicts transfer", 0.88),
        f.evidence(Source.GRIP, "grip released", 0.91),
    ]
    d = f.fuse("transfer_to_tray", ev)
    assert d.verdict is Verdict.VERIFIED
    assert d.confidence > 0.62
    assert d.actionable


def test_single_source_cannot_verify():
    """One signal is never enough, however confident it is."""
    f = EvidenceFuser()
    d = f.fuse("transfer_to_tray", [f.evidence(Source.TEMPORAL_MODEL, "model", 0.99)])
    assert d.verdict is not Verdict.VERIFIED
    assert d.verdict is Verdict.UNCERTAIN


def test_conflicting_evidence_is_uncertain_not_forced():
    f = EvidenceFuser()
    ev = [
        f.evidence(Source.TEMPORAL_MODEL, "model predicts transfer", 0.85),
        f.evidence(Source.ZONE, "hand is in the wrong zone", 0.10),
        f.evidence(Source.GRIP, "no grip change", 0.20),
    ]
    d = f.fuse("transfer_to_tray", ev)
    assert d.verdict is Verdict.UNCERTAIN
    assert not d.actionable


def test_camera_veto_forces_not_observable():
    f = EvidenceFuser()
    ev = [
        f.evidence(Source.ZONE, "hand in tray", 0.99),
        f.evidence(Source.TEMPORAL_MODEL, "model certain", 0.99),
    ]
    d = f.fuse("transfer_to_tray", ev, vetoes=["camera unusable: lens occluded"])
    assert d.verdict is Verdict.NOT_OBSERVABLE
    assert d.confidence == 0.0
    assert not d.actionable


def test_degraded_camera_scales_confidence_down():
    f = EvidenceFuser()
    ev = [
        f.evidence(Source.ZONE, "hand in tray", 0.95),
        f.evidence(Source.TEMPORAL_MODEL, "model agrees", 0.90),
    ]
    good = f.fuse("a", ev, quality_scale=1.0)
    poor = f.fuse("a", ev, quality_scale=0.5)
    assert poor.confidence < good.confidence
    assert poor.verdict is not Verdict.VERIFIED


def test_explanation_lists_every_source():
    f = EvidenceFuser()
    ev = [
        f.evidence(Source.ZONE, "hand in sample_tray", 0.97),
        f.evidence(Source.GRIP, "grip released", 0.91),
        f.evidence(Source.RACK, "rack locked (aruco)", 0.99),
    ]
    text = f.fuse("transfer_to_tray", ev).explain()
    for e in ev:
        assert e.label in text
    assert "fused" in text
    assert "VERIFIED" in text or "UNCERTAIN" in text


def test_reason_is_a_single_line():
    f = EvidenceFuser()
    d = f.fuse("x", [f.evidence(Source.ZONE, "hand in tray", 0.9),
                     f.evidence(Source.GRIP, "grip closed", 0.8)])
    assert "\n" not in d.reason() and d.reason()


def test_rack_veto_on_identity_frame():
    class FakeRack:
        source = "identity"
        confidence = 0.25
    assert rack_veto(FakeRack())
    assert rack_veto(None)

    class Good:
        source = "aruco"
        confidence = 0.95
    assert rack_veto(Good()) == []


def test_camera_veto_helper():
    class Bad:
        usable = False
        reasons = ["lens occluded (90%)"]
    assert camera_veto(Bad())

    class Fine:
        usable = True
        reasons = []
    assert camera_veto(Fine()) == []


def test_default_weights_are_sane():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 0.02
    assert all(0 < w < 0.5 for w in DEFAULT_WEIGHTS.values())


# =================================================================== tracking

def box_at(cx, cy, s=40):
    return (cx - s, cy - s, cx + s, cy + s)


def test_iou_basic():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert 0 < iou((0, 0, 10, 10), (5, 5, 15, 15)) < 1


def test_tracker_keeps_one_id_for_a_moving_object():
    tr = ObjectTracker()
    ids = set()
    for i in range(15):
        tracks = tr.update([Detection("red_box", 0.9, box_at(100 + i * 6, 100))])
        ids.update(t.track_id for t in tracks)
    assert ids == {1}, f"identity should persist, got {ids}"
    assert tr.tracks[1].confirmed


def test_tracker_separates_two_objects():
    tr = ObjectTracker()
    for i in range(8):
        tr.update([
            Detection("red_box", 0.9, box_at(100 + i * 4, 100)),
            Detection("red_box", 0.9, box_at(400 - i * 4, 300)),
        ])
    confirmed = tr.confirmed_tracks()
    assert len(confirmed) == 2
    assert len({t.track_id for t in confirmed}) == 2


def test_tracker_survives_short_occlusion():
    tr = ObjectTracker(max_misses=15)
    for i in range(10):
        tr.update([Detection("red_box", 0.9, box_at(100 + i * 5, 100))])
    for _ in range(6):
        tr.update([])                      # object hidden behind a hand
    assert 1 in tr.tracks, "track must survive a brief occlusion"
    tracks = tr.update([Detection("red_box", 0.9, box_at(180, 100))])
    assert any(t.track_id == 1 for t in tracks), "must re-acquire the same id"


def test_tracker_retires_a_long_lost_object():
    tr = ObjectTracker(max_misses=5)
    for i in range(6):
        tr.update([Detection("red_box", 0.9, box_at(100, 100))])
    for _ in range(10):
        tr.update([])
    assert not tr.tracks


def test_object_state_machine_pick_and_place():
    """Full lifecycle: at rest -> hand arrives -> carried -> settles."""
    tracker = ObjectTracker()
    fsm = ObjectStateMachine(settle_s=0.0)
    zones = ZoneSet([
        Zone("storage", np.array([[0, 0], [0.45, 0], [0.45, 1], [0, 1]], np.float32)),
        Zone("tray", np.array([[0.55, 0], [1, 0], [1, 1], [0.55, 1]], np.float32)),
    ])

    class Rack:
        source = "aruco"
        confidence = 0.95
        def to_rack(self, pts):
            return np.asarray(pts, np.float32) / np.array([640.0, 480.0], np.float32)

    rack = Rack()
    seen = []

    for _ in range(5):                                  # sitting in storage
        t = tracker.update([Detection("sample", 0.9, box_at(120, 240))])
        seen += [x.to for x in fsm.update(t, [], zones, rack)]

    for i in range(12):                                 # carried across
        cx = 120 + i * 30
        t = tracker.update([Detection("sample", 0.9, box_at(cx, 240))])
        seen += [x.to for x in fsm.update(t, [np.array([cx, 240], np.float32)], zones, rack)]

    for _ in range(8):                                  # at rest in the tray
        t = tracker.update([Detection("sample", 0.9, box_at(480, 240))])
        seen += [x.to for x in fsm.update(t, [], zones, rack)]

    assert ObjectState.GRASPED in seen or ObjectState.IN_TRANSIT in seen
    final = tracker.confirmed_tracks()[0]
    assert final.zone == "tray", f"object should end in the tray, got {final.zone}"
    assert final.state in (ObjectState.STORED, ObjectState.RELEASED, ObjectState.PLACED)


def test_illegal_transitions_are_flagged_not_hidden():
    from aegis.perception.tracking import ALLOWED_TRANSITIONS
    assert ObjectState.RELEASED not in ALLOWED_TRANSITIONS[ObjectState.STORED]
    assert ObjectState.GRASPED in ALLOWED_TRANSITIONS[ObjectState.APPROACHED]


# ================================================================ interaction

def synth_hand(label, cx, cy, aperture=1.2):
    pts = np.zeros((21, 2), np.float32)
    pts[0] = [cx, cy]
    pts[5] = [cx + 18, cy - 8]
    pts[17] = [cx - 18, cy - 8]
    pts[9] = [cx, cy - 22]
    reach = 36 * aperture
    for i, tip in enumerate((4, 8, 12, 16, 20)):
        a = -0.9 + i * 0.45
        pts[tip] = [cx + reach * np.cos(a), cy + reach * np.sin(a)]
    for i in range(21):
        if not pts[i].any():
            pts[i] = [cx, cy]
    h = HandObservation(label, 0.9, pts.copy())
    h.points_rack = pts / np.array([640.0, 480.0], np.float32)
    return h


def test_grip_close_and_open_events():
    eng = InteractionEngine()
    zones = ZoneSet()
    out = []
    for i in range(10):                    # open hand
        r = PerceptionResult(i, float(i), hands=[synth_hand("right", 300, 240, 1.5)])
        out += eng.update(r, [], zones, None)
    for i in range(10, 22):                # closing
        r = PerceptionResult(i, float(i), hands=[synth_hand("right", 300, 240, 0.6)])
        out += eng.update(r, [], zones, None)
    assert any(e.type is EventType.GRIP_CLOSE for e in out)

    for i in range(22, 36):                # opening again
        r = PerceptionResult(i, float(i), hands=[synth_hand("right", 300, 240, 1.6)])
        out += eng.update(r, [], zones, None)
    assert any(e.type is EventType.GRIP_OPEN for e in out)


def test_zone_enter_and_exit_events():
    eng = InteractionEngine()
    zones = ZoneSet([
        Zone("storage", np.array([[0, 0], [0.4, 0], [0.4, 1], [0, 1]], np.float32)),
        Zone("tray", np.array([[0.6, 0], [1, 0], [1, 1], [0.6, 1]], np.float32)),
    ])

    class Rack:
        source = "aruco"
        confidence = 0.9
        def to_rack(self, pts):
            return np.asarray(pts, np.float32) / np.array([640.0, 480.0], np.float32)

    out = []
    for i in range(4):
        out += eng.update(PerceptionResult(i, 0, hands=[synth_hand("right", 100, 240)]), [], zones, Rack())
    for i in range(4):
        out += eng.update(PerceptionResult(i, 0, hands=[synth_hand("right", 500, 240)]), [], zones, Rack())

    entered = [e.zone for e in out if e.type is EventType.ZONE_ENTER]
    exited = [e.zone for e in out if e.type is EventType.ZONE_EXIT]
    assert "storage" in entered and "tray" in entered
    assert "storage" in exited


def test_approach_and_contact_events_with_an_object():
    eng = InteractionEngine()
    tracker = ObjectTracker()
    zones = ZoneSet()
    out = []
    for i in range(12):
        tracks = tracker.update([Detection("sample", 0.9, box_at(400, 240, 30))])
        hand_x = 100 + i * 28                       # hand closes on the object
        r = PerceptionResult(i, float(i), hands=[synth_hand("right", hand_x, 240, 1.3)])
        out += eng.update(r, tracks, zones, None)

    types = {e.type for e in out}
    assert EventType.HAND_APPROACH in types
    assert EventType.CONTACT_BEGIN in types


def test_events_carry_their_evidence():
    eng = InteractionEngine()
    out = []
    for i in range(10):
        out += eng.update(PerceptionResult(i, 0, hands=[synth_hand("right", 300, 240, 1.5)]), [], ZoneSet(), None)
    for i in range(10, 22):
        out += eng.update(PerceptionResult(i, 0, hands=[synth_hand("right", 300, 240, 0.6)]), [], ZoneSet(), None)
    closes = [e for e in out if e.type is EventType.GRIP_CLOSE]
    assert closes and "aperture" in closes[0].evidence
    assert closes[0].describe()
    assert closes[0].to_dict()["type"] == "GRIP_CLOSE"


def test_recent_query_filters_by_type():
    eng = InteractionEngine()
    for i in range(10):
        eng.update(PerceptionResult(i, 0, hands=[synth_hand("right", 300, 240, 1.5)]), [], ZoneSet(), None)
    for i in range(10, 22):
        eng.update(PerceptionResult(i, 0, hands=[synth_hand("right", 300, 240, 0.6)]), [], ZoneSet(), None)
    assert eng.has_recent(EventType.GRIP_CLOSE, seconds=60, hand="right")
    assert not eng.has_recent(EventType.OBJECT_LIFTED, seconds=60)


def test_engine_works_with_no_object_detector():
    """Degraded mode: hand-only events must still fire with zero tracks."""
    eng = InteractionEngine()
    zones = ZoneSet([Zone("tray", np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32))])

    class Rack:
        source = "aruco"
        confidence = 0.9
        def to_rack(self, pts):
            return np.asarray(pts, np.float32) / np.array([640.0, 480.0], np.float32)

    out = []
    for i in range(8):
        out += eng.update(PerceptionResult(i, 0, hands=[synth_hand("right", 300, 240)]), [], zones, Rack())
    assert any(e.type is EventType.ZONE_ENTER for e in out)
