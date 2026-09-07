"""Pydantic schemas for immutable startup configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProtocolStep(BaseModel):
    """One ordered experiment-protocol step."""

    id: str
    name: str
    expects: list[str] = Field(min_length=1)
    timeout_s: float = Field(gt=0)
    safety_critical: bool = False
    violation_message: str | None = None
    violation_short_message: str | None = None


class ProtocolConfig(BaseModel):
    """Protocol behavior loaded once at application startup."""

    steps: list[ProtocolStep] = Field(min_length=1)
    debounce_frames: int = Field(default=3, ge=1)
    pending_window_s: float = Field(default=1.0, gt=0)
    lookback_window_s: float = Field(default=2.0, gt=0)
    anomaly_messages: dict[str, str] = Field(default_factory=dict)


class AppConfig(BaseModel):
    """Top-level application settings."""

    protocol_path: str
    pipeline: dict = Field(default_factory=dict)
    outputs: dict = Field(default_factory=dict)
    tts: dict = Field(default_factory=dict)
