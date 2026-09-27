"""
Pydantic DTOs for API request/response validation.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class SessionStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ValidationStatus(str, Enum):
    CORRECT = "CORRECT"
    WARNING = "WARNING"
    SEQUENCE_VIOLATION = "SEQUENCE_VIOLATION"
    DUPLICATE = "DUPLICATE"


# ── User ──────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Experiment steps ──────────────────────────────────────────────────────────

class ExperimentStepIn(BaseModel):
    step_number: Optional[int] = None
    title: Optional[str] = None
    expected_activity: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    safety_critical: bool = False


class ExperimentStepOut(BaseModel):
    id: int
    step_number: int
    title: Optional[str] = None
    expected_activity: str
    description: Optional[str] = None
    safety_critical: bool

    class Config:
        from_attributes = True


# ── Experiment ────────────────────────────────────────────────────────────────

class ExperimentCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    code: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = None
    category: str = "General"
    environment: str = "Microgravity"
    estimated_duration: str = "00:00:00"
    steps: Optional[List[ExperimentStepIn]] = None


class ExperimentOut(BaseModel):
    id: int
    title: str
    code: str
    description: Optional[str] = None
    category: str
    environment: str
    estimated_duration: str
    total_steps: int
    created_at: datetime
    steps: List[ExperimentStepOut] = []

    class Config:
        from_attributes = True


class ExperimentProgressOut(ExperimentOut):
    """Experiment plus live progress derived from its most recent session."""
    status: str                       # Active | Completed | Scheduled | Aborted
    current_step: int
    progress: float                   # 0-100
    latest_session_id: Optional[int] = None
    completed_activities: List[str] = []


# ── Session ───────────────────────────────────────────────────────────────────

class SessionOut(BaseModel):
    id: int
    experiment_id: int
    astronaut_id: Optional[int] = None
    status: SessionStatus
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Activity ──────────────────────────────────────────────────────────────────

class ActivityOut(BaseModel):
    id: int
    session_id: int
    detected_activity: str
    confidence: float
    timestamp: datetime

    class Config:
        from_attributes = True


class ActivityLogOut(BaseModel):
    """Joined activity + log row for the audit table."""
    id: int
    session_id: int
    experiment_code: str
    detected_activity: str
    step_number: Optional[int] = None
    validation_status: ValidationStatus
    confidence: float
    timestamp: datetime


class CurrentActivityOut(BaseModel):
    detected_activity: str
    confidence: float
    expected_activity: Optional[str] = None
    step_number: int
    total_steps: int
    validation_status: ValidationStatus
    timestamp: datetime
    session_id: Optional[int] = None
    progress: float = 0.0
    guidance: Optional[str] = None
    bounding_boxes: List[Dict[str, Any]] = []
    pose_keypoints: List[Dict[str, Any]] = []


# ── Alert ─────────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: int
    session_id: Optional[int] = None
    severity: AlertSeverity
    message: str
    timestamp: datetime
    acknowledged: bool

    class Config:
        from_attributes = True


class AlertSummary(BaseModel):
    total: int
    active: int
    warnings: int
    critical: int


# ── Log ───────────────────────────────────────────────────────────────────────

class LogOut(BaseModel):
    id: int
    session_id: int
    step_number: Optional[int] = None
    activity_id: Optional[int] = None
    validation_status: ValidationStatus
    timestamp: datetime

    class Config:
        from_attributes = True


# ── Dashboard / system ────────────────────────────────────────────────────────

class SystemStatus(BaseModel):
    ai_engine_online: bool
    camera_stream_active: bool
    database_connected: bool
    demo_mode: bool
    confidence_threshold: float
    model_loaded: bool


class TimelineEntry(BaseModel):
    time: str
    event: str


class DashboardStats(BaseModel):
    active_sessions: int
    total_experiments: int
    unacknowledged_alerts: int
    total_activities_today: int
    active_experiment_code: Optional[str] = None
    active_experiment_title: Optional[str] = None
    active_experiment_progress: float = 0.0
    current_activity: Optional[str] = None
    last_activity: Optional[ActivityOut] = None
    recent_timeline: List[TimelineEntry] = []
    system_status: SystemStatus


# ── Monitoring control ────────────────────────────────────────────────────────

class MonitoringStartRequest(BaseModel):
    experiment_id: int
    astronaut_id: Optional[int] = None
    scenario: str = "nominal"


class MonitoringStartResponse(BaseModel):
    session_id: int
    experiment_id: int
    status: str
    scenario: str
    message: str


class MonitoringStopResponse(BaseModel):
    session_id: int
    status: str
    activities_recorded: int
    duration_seconds: float


# ── WebSocket broadcast ───────────────────────────────────────────────────────

class WebSocketPayload(BaseModel):
    timestamp: str
    session_id: Optional[int] = None
    experiment_id: Optional[int] = None
    detected_activity: str
    confidence: float
    expected_step: Optional[str] = None
    step_number: int
    total_steps: int
    status: ValidationStatus
    bounding_boxes: List[Dict[str, Any]] = []
    pose_keypoints: List[Dict[str, Any]] = []
    alert: Optional[Dict[str, Any]] = None
    fsm_state: Optional[str] = None
    progress: float = 0.0
    guidance: Optional[str] = None
    completed_activities: List[str] = []
    # Aerospace Extensions Telemetry
    merkle_hash: Optional[str] = None
    merkle_chain_length: int = 0
    slosh_jerk: float = 0.0
    slosh_alert: bool = False
    eco_mode: str = "ACTIVE"
    eco_fps: float = 30.0
    eco_frames_saved: int = 0
    thermal_status: str = "COOL"
    cpu_percent: float = 0.0
    is_blinded: bool = False
    glare_saturation: float = 0.0
    is_immobile: bool = False
    fod_active: bool = False
    fod_object: str = ""
    fod_eta: float = 0.0
    predicted_impact: Optional[List[int]] = None
    hesitation_active: bool = False
    hesitation_dwell_ms: float = 0.0
    ccsds_last_hex: str = ""
    ccsds_total_packets: int = 0
    hand_pos: Optional[List[float]] = None


# ── Assistant ─────────────────────────────────────────────────────────────────

class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[int] = None


class AssistantChatResponse(BaseModel):
    reply: str
    context: Optional[Dict[str, Any]] = None
    timestamp: datetime


class AssistantSuggestionsResponse(BaseModel):
    suggestions: List[str]
