from har.fusion.interaction_engine import InteractionEngine
from har.vision.mediapipe_wrapper import HandState, Landmark
from har.vision.yolo_wrapper import Detection


def hand(pinch: bool) -> HandState:
    points = [Landmark(0.2, 0.2) for _ in range(21)]
    points[4] = Landmark(0.30, 0.30)
    points[8] = Landmark(0.31 if pinch else 0.50, 0.31 if pinch else 0.50)
    return HandState({"right": tuple(points)}, (100, 100), 1.0)


def test_fusion_emits_only_state_changes_using_relational_overlap():
    detection = Detection("vial", 0.9, (15, 15, 40, 40), 2)
    engine = InteractionEngine(grasp_distance=0.05)
    assert engine.update(hand(True), [detection])[0].state == "grasp_start"
    assert engine.update(hand(True), [detection]) == []
    assert engine.update(hand(False), [detection])[0].state == "contact"
