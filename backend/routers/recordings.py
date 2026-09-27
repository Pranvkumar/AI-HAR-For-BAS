"""
Session Video Recordings Router — List and download MP4 mission recordings.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from services.video_recorder import session_video_recorder, RECORDINGS_DIR

router = APIRouter(prefix="/api/v1/recordings", tags=["recordings"])


@router.get("/list")
def list_recordings():
    return {"recordings": session_video_recorder.list_recordings()}


@router.get("/download/{filename}")
def download_recording(filename: str):
    file_path = RECORDINGS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Recording not found")
    return FileResponse(
        path=str(file_path),
        media_type="video/mp4",
        filename=filename,
    )
