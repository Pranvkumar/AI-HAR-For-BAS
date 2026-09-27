"""
Logs router — experiment audit trail.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_session
from db import models
from schemas.dto import ActivityLogOut, ValidationStatus

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


@router.get("", response_model=List[ActivityLogOut])
def list_logs(
    session_id: Optional[int] = Query(None),
    experiment_code: Optional[str] = Query(None),
    validation_status: Optional[str] = Query(None),
    include_duplicates: bool = Query(False),
    limit: int = Query(200, le=2000),
    db: Session = Depends(get_session),
):
    """
    Audit entries joining each log row to its activity and experiment.

    Duplicate rows are excluded by default — they are the expected result of
    re-detecting the same step across consecutive frames, not audit events.
    """
    query = (
        db.query(
            models.ExperimentLog.id,
            models.ExperimentLog.session_id,
            models.ExperimentLog.step_number,
            models.ExperimentLog.validation_status,
            models.ExperimentLog.timestamp,
            models.Activity.detected_activity,
            models.Activity.confidence,
            models.Experiment.code,
        )
        .join(models.Activity, models.ExperimentLog.activity_id == models.Activity.id)
        .join(
            models.ExperimentSession,
            models.ExperimentLog.session_id == models.ExperimentSession.id,
        )
        .join(
            models.Experiment,
            models.ExperimentSession.experiment_id == models.Experiment.id,
        )
    )

    if session_id is not None:
        query = query.filter(models.ExperimentLog.session_id == session_id)
    if experiment_code:
        query = query.filter(models.Experiment.code == experiment_code)
    if validation_status:
        query = query.filter(
            models.ExperimentLog.validation_status == validation_status.upper()
        )
    elif not include_duplicates:
        query = query.filter(models.ExperimentLog.validation_status != "DUPLICATE")

    rows = query.order_by(models.ExperimentLog.timestamp.desc()).limit(limit).all()

    return [
        ActivityLogOut(
            id=row.id,
            session_id=row.session_id,
            experiment_code=row.code,
            detected_activity=row.detected_activity,
            step_number=row.step_number,
            validation_status=ValidationStatus(row.validation_status),
            confidence=row.confidence,
            timestamp=row.timestamp,
        )
        for row in rows
    ]
