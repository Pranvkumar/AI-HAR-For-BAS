"""
Object Registry Router — Capture, register, and manage dynamic objects for ORB detection.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.object_registry import dynamic_object_registry
from services.monitoring_service import camera_manager

router = APIRouter(prefix="/api/v1/objects", tags=["objects"])


class CaptureRequest(BaseModel):
    object_slug: str


class RegisterRequest(BaseModel):
    object_slug: str
    display_name: str


@router.get("/list")
def list_objects():
    return {"objects": dynamic_object_registry.list_objects()}


@router.post("/capture")
def capture_object_image(req: CaptureRequest):
    frame = camera_manager.read_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="Camera sensor not ready — no frame available")

    slug = req.object_slug.lower().replace(" ", "_").replace("-", "_")
    count = dynamic_object_registry.capture_frame(slug, frame)
    return {
        "status": "ok",
        "slug": slug,
        "count": count,
        "message": f"Captured frame #{count} for '{slug}'"
    }


@router.post("/register")
def register_object(req: RegisterRequest):
    slug = req.object_slug.lower().replace(" ", "_").replace("-", "_")
    try:
        manifest = dynamic_object_registry.finalize_registration(slug, req.display_name)
        return {"status": "ok", "manifest": manifest}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/delete/{slug}")
def delete_object(slug: str):
    success = dynamic_object_registry.delete_object(slug)
    if not success:
        raise HTTPException(status_code=404, detail=f"Object '{slug}' not found")
    return {"status": "ok", "deleted": slug}
