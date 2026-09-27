"""
Aerospace Capabilities Router — Exposes CCSDS, Merkle Ledger, Thermal, Eco, and Safety Telemetry.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.merkle_ledger import flight_merkle_ledger
from services.ccsds_formatter import ccsds_formatter
from services.biometric_service import biometric_manager
from services.aerospace_safety import (
    thermal_governor,
    hardware_watchdog,
    glare_detector,
    immobility_detector,
    drift_detector,
    slosh_guard,
    eco_governor,
    cognitive_stall_detector,
)
from services.voice_alert import tts_worker

router = APIRouter(prefix="/api/v1/aerospace", tags=["aerospace"])


class SpeakRequest(BaseModel):
    text: str


class VerifyRequest(BaseModel):
    action: str = "scan"  # "scan" or "bypass"
    crew_name: str = "Commander (AEGIS-01)"


@router.get("/telemetry")
def get_aerospace_telemetry():
    """Returns combined aerospace extensions state for HUD and ground control."""
    thermal_governor.check()
    hardware_watchdog.feed()

    return {
        "merkle": {
            "chain_hash": flight_merkle_ledger.get_short_hash(),
            "full_hash": flight_merkle_ledger.current_hash,
            "chain_length": flight_merkle_ledger.chain_length,
            "recent_blocks": flight_merkle_ledger.get_last_n_blocks(3),
            "verified": flight_merkle_ledger.verify_chain(),
        },
        "ccsds": ccsds_formatter.get_stats(),
        "thermal": thermal_governor.get_state(),
        "watchdog": hardware_watchdog.get_state(),
        "eco": {
            "mode": eco_governor.mode,
            "target_fps": eco_governor.target_fps,
            "frames_skipped": eco_governor.frames_skipped,
        },
        "slosh": {
            "jerk_magnitude": slosh_guard.jerk_magnitude,
            "alert": slosh_guard.alert_active,
            "alert_text": slosh_guard.alert_text,
            "threshold": slosh_guard.jerk_threshold,
        },
        "glare": {
            "is_blinded": glare_detector.is_blinded,
            "saturation_ratio": glare_detector.saturation_ratio,
        },
        "immobility": {
            "is_immobile": immobility_detector.is_immobile,
            "current_variance": immobility_detector.current_variance,
        },
        "fod": {
            "active": drift_detector.fod_active,
            "object": drift_detector.fod_object,
            "eta_s": drift_detector.fod_eta,
            "predicted_impact": drift_detector.predicted_impact,
        },
        "hesitation": {
            "active": cognitive_stall_detector.is_hesitating,
            "dwell_ms": cognitive_stall_detector.dwell_ms,
            "count": cognitive_stall_detector.hesitation_count,
        },
        "biometrics": biometric_manager.get_state(),
    }


@router.post("/biometrics/verify")
def manage_biometrics(req: VerifyRequest):
    if req.action == "bypass":
        biometric_manager.unlock_bypass()
    else:
        biometric_manager.start_verification(req.crew_name)
    return biometric_manager.get_state()


@router.post("/tts/speak")
def speak_cue(req: SpeakRequest):
    tts_worker.speak(req.text)
    return {"status": "ok", "spoken": req.text}


@router.get("/merkle/verify")
def verify_merkle():
    valid = flight_merkle_ledger.verify_chain()
    return {
        "valid": valid,
        "chain_length": flight_merkle_ledger.chain_length,
        "head_hash": flight_merkle_ledger.current_hash,
    }
