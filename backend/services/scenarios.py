"""
Demo scenario generation.

Scenarios are derived from an experiment's own expected sequence rather than a
fixed activity list, so any seeded experiment can be demoed. Each scenario
exercises one FSM path: nominal (all CORRECT), low_confidence (WARNING), and
violation (SEQUENCE_VIOLATION).
"""
import random
from typing import List, Sequence, Tuple

# Confidence bands relative to the configured threshold.
HIGH_CONFIDENCE = (0.86, 0.96)
LOW_CONFIDENCE = (0.48, 0.66)

ScenarioStep = Tuple[str, float]

SCENARIO_NAMES = ("nominal", "low_confidence", "violation")

SCENARIO_DESCRIPTIONS = {
    "nominal": "Correct order at high confidence — every step validates.",
    "low_confidence": "Correct order but unreliable detections — raises warnings.",
    "violation": "A step performed out of order — raises a critical alert.",
}


def _sample(band: Tuple[float, float]) -> float:
    return round(random.uniform(*band), 3)


def build_scenario(sequence: Sequence[str], scenario: str) -> List[ScenarioStep]:
    """
    Build a scripted (activity, confidence) list for the given sequence.

    Args:
        sequence: The experiment's expected activities, in order.
        scenario: One of SCENARIO_NAMES.
    """
    steps = list(sequence)
    if not steps:
        return []

    if scenario == "low_confidence":
        return [(activity, _sample(LOW_CONFIDENCE)) for activity in steps]

    if scenario == "violation" and len(steps) >= 3:
        # Jump the final step forward so it lands before its prerequisites.
        # This is the classic "sealed the container before pouring" error.
        reordered = steps[:2] + [steps[-1]] + steps[2:-1]
        return [(activity, _sample(HIGH_CONFIDENCE)) for activity in reordered]

    return [(activity, _sample(HIGH_CONFIDENCE)) for activity in steps]
