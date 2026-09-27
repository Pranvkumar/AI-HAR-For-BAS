"""
Temporal Human Activity Recognition.

Scores BAS experiment activities from a buffered sequence of frame features
(detections, poses, hand tracks). This is a heuristic implementation that
matches the BaseTemporalHAR contract, so a trained temporal model can replace
it without touching the pipeline.

Supported activities align with experiment_steps.expected_activity:
  PICK_CONTAINER, OPEN_CONTAINER, POUR_SAMPLE,
  MIX_SAMPLE, PLACE_CONTAINER, CLOSE_CONTAINER
"""
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseTemporalHAR, FrameBuffer

SUPPORTED_ACTIVITIES = [
    "PICK_CONTAINER",
    "OPEN_CONTAINER",
    "POUR_SAMPLE",
    "MIX_SAMPLE",
    "PLACE_CONTAINER",
    "CLOSE_CONTAINER",
    "RETRIEVE_RED_BOX",
    "RETRIEVE_SECOND_COLORED_BOX",
    "RETURN_RED_BOX",
    "RETURN_SECOND_COLORED_BOX",
]

IDLE_ACTIVITY = "IDLE"

# Per-activity weights over the motion features computed below.
# Keys map to fields of the aggregated feature dict.
ACTIVITY_WEIGHTS: Dict[str, Dict[str, float]] = {
    "PICK_CONTAINER":  {"grasping": 0.5, "descending": 0.3, "proximity": 0.2},
    "OPEN_CONTAINER":  {"grasping": 0.6, "proximity": 0.4},
    "POUR_SAMPLE":     {"grasping": 0.3, "descending": 0.4, "proximity": 0.3},
    "MIX_SAMPLE":      {"grasping": 0.4, "lateral_motion": 0.4, "proximity": 0.2},
    "PLACE_CONTAINER": {"grasping": 0.3, "ascending": 0.4, "proximity": 0.3},
    "CLOSE_CONTAINER": {"grasping": 0.5, "proximity": 0.5},
    "RETRIEVE_RED_BOX": {"grasping": 0.5, "descending": 0.3, "proximity": 0.2},
    "RETRIEVE_SECOND_COLORED_BOX": {"grasping": 0.5, "descending": 0.3, "proximity": 0.2},
    "RETURN_RED_BOX": {"grasping": 0.4, "ascending": 0.3, "proximity": 0.3},
    "RETURN_SECOND_COLORED_BOX": {"grasping": 0.4, "ascending": 0.3, "proximity": 0.3},
}


def _bbox_center(bbox: List[float]) -> Tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0


def extract_motion_features(sequence: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Reduce a frame sequence to normalized motion features in [0, 1].

    - proximity:      fraction of frames where a hand was near a target object
    - grasping:       fraction of frames with a confident grasp interaction
    - descending:     normalized downward vertical hand travel
    - ascending:      normalized upward vertical hand travel
    - lateral_motion: normalized horizontal hand travel (proxy for stirring)
    """
    frame_count = len(sequence)
    if frame_count == 0:
        return {k: 0.0 for k in
                ("proximity", "grasping", "descending", "ascending", "lateral_motion")}

    proximity_frames = 0
    grasping_frames = 0
    centers: List[Tuple[float, float]] = []

    for frame in sequence:
        tracks = [t for t in frame.get("tracker_output", []) if t.get("class_name") == "hand"]
        if not tracks:
            continue

        frame_near = False
        frame_grasp = False
        for track in tracks:
            interaction = track.get("interaction", {})
            if interaction.get("interacting"):
                frame_near = True
            if interaction.get("interaction_type") == "grasping":
                frame_grasp = True

        proximity_frames += int(frame_near)
        grasping_frames += int(frame_grasp)
        centers.append(_bbox_center(tracks[0].get("bbox", [0.5, 0.5, 0.5, 0.5])))

    descending = ascending = lateral = 0.0
    for (prev_x, prev_y), (curr_x, curr_y) in zip(centers, centers[1:]):
        dy = curr_y - prev_y
        if dy > 0:
            descending += dy
        else:
            ascending += -dy
        lateral += abs(curr_x - prev_x)

    # Travel is scaled so that ~0.5 of normalized frame height saturates the feature.
    def _scale(value: float) -> float:
        return min(value / 0.5, 1.0)

    return {
        "proximity": proximity_frames / frame_count,
        "grasping": grasping_frames / frame_count,
        "descending": _scale(descending),
        "ascending": _scale(ascending),
        "lateral_motion": _scale(lateral),
    }


class TemporalHAR(BaseTemporalHAR):
    """
    Heuristic temporal activity recognizer over buffered frame features.
    """

    def __init__(
        self,
        frame_buffer: Optional[FrameBuffer] = None,
        confidence_threshold: float = 0.70,
    ):
        """
        Args:
            frame_buffer: Buffer supplying the default sequence for predict().
            confidence_threshold: Reported for callers; predict() always returns
                its best score so the FSM can apply the threshold policy.
        """
        self.frame_buffer = frame_buffer
        self.confidence_threshold = confidence_threshold
        self._loaded = True

    def predict(
        self,
        feature_sequence: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, float]:
        """
        Predict the activity for a frame sequence.

        Args:
            feature_sequence: Frame features; falls back to the frame buffer.

        Returns:
            (activity_name, confidence). Returns (IDLE, 0.0) with no usable data.
        """
        if feature_sequence is None:
            feature_sequence = self.frame_buffer.get_sequence() if self.frame_buffer else []

        if not feature_sequence:
            return IDLE_ACTIVITY, 0.0

        features = extract_motion_features(feature_sequence)

        scores = {
            activity: sum(features[feat] * weight for feat, weight in weights.items())
            for activity, weights in ACTIVITY_WEIGHTS.items()
        }

        best_activity = max(scores, key=scores.get)
        best_score = scores[best_activity]

        if best_score <= 0.0:
            return IDLE_ACTIVITY, 0.0

        return best_activity, round(min(best_score, 1.0), 3)

    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def supported_activities(self) -> List[str]:
        return list(SUPPORTED_ACTIVITIES)
