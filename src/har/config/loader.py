"""Typed protocol configuration loading with a Pydantic-compatible boundary."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProtocolStep:
    id: int | str
    name: str
    expects: dict[str, Any]
    timeout_s: float
    safety_critical: bool = False
    watch_objects: tuple[str, ...] = field(default_factory=tuple)
    violation_message: str | None = None


@dataclass(frozen=True)
class ProtocolConfig:
    steps: list[ProtocolStep]
    debounce_frames: int = 3
    pending_window_s: float = 2.0
    lookback_window_s: float = 5.0


def load_protocol(path: str | Path) -> ProtocolConfig:
    """Load a protocol once and reject malformed step definitions."""
    with Path(path).open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}
    steps = []
    for item in raw.get("steps", []):
        required = ("id", "name", "expects", "timeout_s")
        missing = [key for key in required if key not in item]
        if missing:
            raise ValueError(f"protocol step missing keys: {missing}")
        steps.append(
            ProtocolStep(
                id=item["id"],
                name=str(item["name"]),
                expects=dict(item["expects"]),
                timeout_s=float(item["timeout_s"]),
                safety_critical=bool(item.get("safety_critical", False)),
                watch_objects=tuple(str(value) for value in item.get("watch_objects", [])),
                violation_message=(str(item["violation_message"]) if item.get("violation_message") else None),
            )
        )
    if not steps:
        raise ValueError("protocol must contain at least one step")
    return ProtocolConfig(
        steps=steps,
        debounce_frames=int(raw.get("debounce_frames", 3)),
        pending_window_s=float(raw.get("pending_window_s", 2.0)),
        lookback_window_s=float(raw.get("lookback_window_s", 5.0)),
    )
