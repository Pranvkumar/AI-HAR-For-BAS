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


def test_fusion_derives_relational_red_blue_events():
    points = [Landmark(0.5, 0.5) for _ in range(21)]
    points[4] = Landmark(0.48, 0.48)
    points[8] = Landmark(0.49, 0.49)
    hand_state = HandState({"right": tuple(points)}, (200, 200), 1.0)
    detections = [
        Detection("red_box", 0.9, (40, 130, 80, 170), 1),
        Detection("red_box", 0.9, (120, 130, 160, 170), 2),
        Detection("blue_box", 0.9, (44, 95, 76, 127), 3),
        Detection("blue_box", 0.9, (124, 95, 156, 127), 4),
    ]
    engine = InteractionEngine(grasp_distance=0.05)
    events = engine.update(hand_state, detections)
    objects = {event.object for event in events}
    assert "red_box_pair" in objects
    assert "blue_box_stack" in objects
