"""
System router — operational health and environmental telemetry.
"""
from typing import Any, Dict

from fastapi import APIRouter

from routers.dashboard import build_system_status
from schemas.dto import SystemStatus
from services.environment_service import build_environment

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/status", response_model=SystemStatus)
def get_system_status():
    """Current status of the AI engine, camera stream and database."""
    return build_system_status()


@router.get("/environment")
def get_environment() -> Dict[str, Any]:
    """
    Simulated microgravity environment telemetry.

    Marked `simulated: true` — these are demo values, not BAS measurements.
    """
    return build_environment()
