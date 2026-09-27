"""
Simulated environmental telemetry for the microgravity status page.

These are synthetic values, not real BAS measurements — the UI labels them as
such. They live server-side so the whole frontend reads from one source, and so
a real sensor feed can replace this module without any UI change.
"""
import math
import random
import time
from typing import Any, Dict, List

# Sample count in each trend sparkline.
TREND_POINTS = 12

# (label, baseline, unit, jitter, decimals)
TREND_SPECS = [
    ("Environmental Stability", 97.0, "%", 1.5, 0),
    ("Motion Disturbance", 12.0, "µg", 3.0, 0),
    ("Temperature", 22.4, "°C", 0.2, 1),
    ("Humidity", 45.0, "%", 1.5, 0),
]

# (label, baseline, max, unit, jitter, decimals)
GAUGE_SPECS = [
    ("G-Level", 0.0001, 0.001, "g", 0.00002, 6),
    ("Vibration", 15.0, 100.0, "µg", 4.0, 1),
    ("Air Pressure", 101.3, 120.0, "kPa", 0.4, 1),
    ("Radiation", 0.32, 1.0, "mSv/d", 0.05, 2),
]


def _drift(baseline: float, jitter: float, phase: float) -> float:
    """Slow sine drift plus small noise — reads like a sensor, not a random walk."""
    return baseline + math.sin(phase) * jitter * 0.6 + random.uniform(-jitter, jitter) * 0.4


def build_environment() -> Dict[str, Any]:
    """Generate one snapshot of environmental telemetry."""
    now = time.time()

    metrics = [
        {"label": "Microgravity Status", "value": "Nominal",
         "detail": "Gravity level within expected parameters"},
        {"label": "Experiment Stability", "value": "Stable",
         "detail": "No significant disturbances detected"},
        {"label": "Monitoring State", "value": "Active",
         "detail": "All sensors reporting normally"},
        {"label": "Data Quality", "value": "Good",
         "detail": "Sensor calibration within tolerance"},
    ]

    trends: List[Dict[str, Any]] = []
    for index, (label, baseline, unit, jitter, decimals) in enumerate(TREND_SPECS):
        series = [
            round(_drift(baseline, jitter, now / 30 + index + point / 3), decimals)
            for point in range(TREND_POINTS)
        ]
        trends.append({
            "label": label,
            "value": series[-1],
            "unit": unit,
            "data": series,
        })

    gauges = [
        {
            "label": label,
            "value": round(max(_drift(baseline, jitter, now / 40 + index), 0.0), decimals),
            "max": maximum,
            "unit": unit,
            "status": "nominal",
        }
        for index, (label, baseline, maximum, unit, jitter, decimals) in enumerate(GAUGE_SPECS)
    ]

    return {
        "metrics": metrics,
        "trends": trends,
        "gauges": gauges,
        "environmental_stability": trends[0]["value"],
        "motion_disturbance": "Low" if trends[1]["value"] < 20 else "Elevated",
        "experiment_environment": "Nominal",
        "simulated": True,
    }
