"""
Dashboard router — aggregate telemetry for mission control.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import settings
from db.session import get_session
from db import models
from schemas.dto import (
    ActivityOut,
    DashboardStats,
    SystemStatus,
    TimelineEntry,
)
from services.experiment_service import ExperimentService
from services.monitoring_service import monitoring_service

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

# How many recent events the overview timeline shows.
TIMELINE_LIMIT = 8


def build_system_status() -> SystemStatus:
    """Current operational status of the monitoring stack."""
    return SystemStatus(
        ai_engine_online=True,
        camera_stream_active=monitoring_service.get_active_session_count() > 0,
        database_connected=True,
        demo_mode=settings.DEMO_MODE,
        confidence_threshold=settings.CONFIDENCE_THRESHOLD,
        model_loaded=True,
    )


def _humanize(activity: str) -> str:
    return activity.replace("_", " ").title()


def _build_timeline(db: Session) -> List[TimelineEntry]:
    """Recent validated events, newest first, as display strings."""
    rows = (
        db.query(
            models.Activity.timestamp,
            models.Activity.detected_activity,
            models.ExperimentLog.validation_status,
        )
        .join(
            models.ExperimentLog,
            models.ExperimentLog.activity_id == models.Activity.id,
        )
        # Duplicates are frame-rate noise, not events worth showing the crew.
        .filter(models.ExperimentLog.validation_status != "DUPLICATE")
        .order_by(models.Activity.timestamp.desc())
        .limit(TIMELINE_LIMIT)
        .all()
    )

    phrasing = {
        "CORRECT": "{activity} confirmed",
        "WARNING": "{activity} detection unclear",
        "SEQUENCE_VIOLATION": "Sequence violation: {activity} out of order",
    }

    return [
        TimelineEntry(
            time=timestamp.strftime("%H:%M:%S"),
            event=phrasing.get(status, "{activity} detected").format(
                activity=_humanize(activity)
            ),
        )
        for timestamp, activity, status in rows
    ]


@router.get("", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_session)):
    """Aggregate counts, active experiment summary and system status."""
    active_sessions = (
        db.query(models.ExperimentSession)
        .filter(models.ExperimentSession.status == "IN_PROGRESS")
        .count()
    )
    total_experiments = db.query(models.Experiment).count()
    unacknowledged_alerts = (
        db.query(models.Alert)
        .filter(models.Alert.acknowledged.is_(False))
        .count()
    )

    since = datetime.now(timezone.utc) - timedelta(days=1)
    total_activities_today = (
        db.query(models.Activity)
        .filter(models.Activity.timestamp >= since)
        .count()
    )

    last_activity = (
        db.query(models.Activity)
        .order_by(models.Activity.timestamp.desc())
        .first()
    )

    # Prefer a running session for the headline experiment; otherwise fall back
    # to the most recently created one so the overview is never empty.
    active_code: Optional[str] = None
    active_title: Optional[str] = None
    active_progress = 0.0
    current_activity: Optional[str] = None

    active = monitoring_service.get_any_session()
    headline_experiment = None

    if active is not None:
        headline_experiment = ExperimentService.get_by_id(db, active.experiment_id)
        current_activity = _humanize(active.fsm.last_detected_activity or "")
    else:
        headline_experiment = (
            db.query(models.Experiment)
            .order_by(models.Experiment.code)
            .first()
        )
        if last_activity:
            current_activity = _humanize(last_activity.detected_activity)

    if headline_experiment is not None:
        summary = ExperimentService.with_progress(db, headline_experiment)
        active_code = summary.code
        active_title = summary.title
        active_progress = summary.progress

    return DashboardStats(
        active_sessions=active_sessions,
        total_experiments=total_experiments,
        unacknowledged_alerts=unacknowledged_alerts,
        total_activities_today=total_activities_today,
        active_experiment_code=active_code,
        active_experiment_title=active_title,
        active_experiment_progress=active_progress,
        current_activity=current_activity or None,
        last_activity=ActivityOut.model_validate(last_activity) if last_activity else None,
        recent_timeline=_build_timeline(db),
        system_status=build_system_status(),
    )
