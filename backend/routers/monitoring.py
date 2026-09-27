"""
Monitoring router — session lifecycle and current activity state.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.session import get_session
from db import models
from schemas.dto import (
    CurrentActivityOut,
    MonitoringStartRequest,
    MonitoringStartResponse,
    MonitoringStopResponse,
    SessionOut,
    ValidationStatus,
)
from services.monitoring_service import monitoring_service
from services.scenarios import SCENARIO_DESCRIPTIONS, SCENARIO_NAMES, build_scenario

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


@router.post("/start", response_model=MonitoringStartResponse)
async def start_monitoring(
    request: MonitoringStartRequest,
    db: Session = Depends(get_session),
):
    """Start a monitoring session for an experiment."""
    experiment = (
        db.query(models.Experiment)
        .filter(models.Experiment.id == request.experiment_id)
        .first()
    )
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    if request.scenario not in SCENARIO_NAMES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown scenario '{request.scenario}'. Valid: {list(SCENARIO_NAMES)}",
        )

    step_count = (
        db.query(models.ExperimentStep)
        .filter(models.ExperimentStep.experiment_id == request.experiment_id)
        .count()
    )
    if step_count == 0:
        raise HTTPException(
            status_code=422,
            detail="Experiment has no steps defined; nothing to monitor",
        )

    db_session = await monitoring_service.start_session(
        db=db,
        experiment_id=request.experiment_id,
        astronaut_id=request.astronaut_id,
        scenario=request.scenario,
    )

    return MonitoringStartResponse(
        session_id=db_session.id,
        experiment_id=request.experiment_id,
        status=db_session.status,
        scenario=request.scenario,
        message=f"Monitoring session {db_session.id} started ({request.scenario} scenario)",
    )


@router.post("/stop/{session_id}", response_model=MonitoringStopResponse)
async def stop_monitoring(session_id: int, db: Session = Depends(get_session)):
    """Stop an active monitoring session."""
    active = monitoring_service.get_session(session_id)
    if not active:
        raise HTTPException(status_code=404, detail="No active session with this ID")

    started_at = active.started_at
    activities_recorded = active.activities_recorded

    db_session = await monitoring_service.stop_session(db, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    duration = (datetime.now(timezone.utc) - started_at).total_seconds()

    return MonitoringStopResponse(
        session_id=session_id,
        status=db_session.status,
        activities_recorded=activities_recorded,
        duration_seconds=round(duration, 2),
    )


@router.get("/activities/current", response_model=CurrentActivityOut)
def get_current_activity(db: Session = Depends(get_session)):
    """
    Most recent detection, including overlay geometry.

    Prefers the live payload from the inference loop; falls back to the last
    persisted activity so the panel still renders after a session ends.
    """
    payload = monitoring_service.last_payload
    if payload is not None:
        return CurrentActivityOut(
            detected_activity=payload.detected_activity,
            confidence=payload.confidence,
            expected_activity=payload.expected_step,
            step_number=payload.step_number,
            total_steps=payload.total_steps,
            validation_status=payload.status,
            timestamp=datetime.fromisoformat(payload.timestamp),
            session_id=payload.session_id,
            progress=payload.progress,
            guidance=payload.guidance,
            bounding_boxes=payload.bounding_boxes,
            pose_keypoints=payload.pose_keypoints,
        )

    activity = (
        db.query(models.Activity)
        .order_by(models.Activity.timestamp.desc())
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail="No activities recorded yet")

    log = (
        db.query(models.ExperimentLog)
        .filter(models.ExperimentLog.activity_id == activity.id)
        .first()
    )
    total_steps = (
        db.query(models.ExperimentStep)
        .join(
            models.ExperimentSession,
            models.ExperimentSession.experiment_id == models.ExperimentStep.experiment_id,
        )
        .filter(models.ExperimentSession.id == activity.session_id)
        .count()
    )

    return CurrentActivityOut(
        detected_activity=activity.detected_activity,
        confidence=activity.confidence,
        expected_activity=None,
        step_number=(log.step_number if log else 0) or 0,
        total_steps=total_steps,
        validation_status=(
            ValidationStatus(log.validation_status) if log else ValidationStatus.WARNING
        ),
        timestamp=activity.timestamp,
        session_id=activity.session_id,
        progress=0.0,
        bounding_boxes=[],
        pose_keypoints=[],
    )


@router.get("/sessions", response_model=List[SessionOut])
def list_sessions(limit: int = Query(50, le=200), db: Session = Depends(get_session)):
    """List recent experiment sessions, newest first."""
    return (
        db.query(models.ExperimentSession)
        .order_by(models.ExperimentSession.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/scenarios")
def list_scenarios() -> Dict[str, Any]:
    """Available demo scenarios with a description of the FSM path each drives."""
    return {
        "scenarios": [
            {"name": name, "description": SCENARIO_DESCRIPTIONS[name]}
            for name in SCENARIO_NAMES
        ]
    }


@router.get("/scenarios/{scenario}/preview")
def preview_scenario(
    scenario: str,
    experiment_id: int = Query(...),
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Preview the activity script a scenario would drive for an experiment."""
    if scenario not in SCENARIO_NAMES:
        raise HTTPException(status_code=404, detail="Unknown scenario")

    steps = (
        db.query(models.ExperimentStep)
        .filter(models.ExperimentStep.experiment_id == experiment_id)
        .order_by(models.ExperimentStep.step_number)
        .all()
    )
    if not steps:
        raise HTTPException(status_code=404, detail="Experiment has no steps")

    sequence = [s.expected_activity for s in steps]
    return {
        "scenario": scenario,
        "description": SCENARIO_DESCRIPTIONS[scenario],
        "expected_sequence": sequence,
        "script": [
            {"activity": activity, "confidence": confidence}
            for activity, confidence in build_scenario(sequence, scenario)
        ],
    }


@router.get("/stream")
async def stream_live_feed():
    """Live MJPEG video stream endpoint for HUD and camera feed visualization."""
    from fastapi.responses import StreamingResponse
    import asyncio

    async def generate_mjpeg():
        while True:
            jpeg = monitoring_service.get_latest_jpeg()
            if jpeg:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                )
            await asyncio.sleep(0.066)

    return StreamingResponse(
        generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
