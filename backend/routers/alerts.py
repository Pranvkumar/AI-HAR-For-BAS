"""
Alerts router — safety alert listing, summary and acknowledgment.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.session import get_session
from db import models
from schemas.dto import AlertOut, AlertSummary

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("", response_model=List[AlertOut])
def list_alerts(
    session_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_session),
):
    """List alerts, newest first, with optional filters."""
    query = db.query(models.Alert)

    if session_id is not None:
        query = query.filter(models.Alert.session_id == session_id)
    if severity:
        query = query.filter(models.Alert.severity == severity.upper())
    if acknowledged is not None:
        query = query.filter(models.Alert.acknowledged.is_(acknowledged))

    return query.order_by(models.Alert.timestamp.desc()).limit(limit).all()


@router.get("/summary", response_model=AlertSummary)
def alert_summary(db: Session = Depends(get_session)):
    """Counts for the alert KPI cards."""
    base = db.query(models.Alert)

    return AlertSummary(
        total=base.count(),
        active=base.filter(models.Alert.acknowledged.is_(False)).count(),
        warnings=base.filter(models.Alert.severity == "WARNING").count(),
        critical=base.filter(models.Alert.severity == "CRITICAL").count(),
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_session)):
    """Mark an alert as acknowledged by the crew."""
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.acknowledged = True
    db.commit()
    db.refresh(alert)
    return alert
