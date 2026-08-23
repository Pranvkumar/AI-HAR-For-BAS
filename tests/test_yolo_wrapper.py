from har.vision.yolo_wrapper import Detection


def test_detection_is_normalized_and_immutable():
    detection = Detection("vial", 0.9, (1.0, 2.0, 3.0, 4.0), 7)
    assert detection.cls == "vial"
    assert detection.track_id == 7
